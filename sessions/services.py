from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction, IntegrityError
from django.utils import timezone

from tables.models import Table, PricingRule, AdditionalFee
from packages.models import Package
from shifts.models import Shift
from users.models import User

from .models import PlaySession, SessionTableLog


class SessionService:
    """Service layer untuk operasi bisnis PlaySession & SessionTableLog."""

    # ------------------------------------------------------------------
    # Open Session
    # ------------------------------------------------------------------
    @staticmethod
    def open_session(
        *,
        outlet_id: int,
        shift_id: int,
        customer_name: str,
        customer_phone: str,
        initial_table_id: int,
        officer_start_id: int,
        package_id: int | None = None,
    ) -> PlaySession:
        """
        Buka sesi bermain baru.

        - Validasi shift masih open
        - Validasi meja available
        - Validasi package (jika ada) milik outlet yang sama
        - Buka PlaySession + SessionTableLog pertama
        - Set meja jadi occupied
        """
        # Validasi shift
        try:
            shift = Shift.objects.select_related('outlet').get(pk=shift_id)
        except Shift.DoesNotExist:
            raise ValidationError({'shift': 'Shift does not exist.'})
        if shift.status != Shift.Status.OPEN:
            raise ValidationError({'shift': 'Shift is not open.'})
        if shift.outlet_id != outlet_id:
            raise ValidationError({'shift': 'Shift does not belong to this outlet.'})

        # Validasi meja (lightweight: existence + outlet only)
        try:
            table = Table.objects.only('id', 'outlet_id').get(pk=initial_table_id)
        except Table.DoesNotExist:
            raise ValidationError({'initial_table': 'Table does not exist.'})
        if table.outlet_id != outlet_id:
            raise ValidationError({'initial_table': 'Table does not belong to this outlet.'})

        # Validasi package (jika ada)
        package = None
        if package_id:
            try:
                package = Package.objects.get(pk=package_id)
            except Package.DoesNotExist:
                raise ValidationError({'package': 'Package does not exist.'})
            if package.outlet_id != outlet_id:
                raise ValidationError({'package': 'Package does not belong to this outlet.'})
            if not package.is_active:
                raise ValidationError({'package': 'Package is not active.'})

        with transaction.atomic():
            # Lock table row dan validasi availability secara atomik
            locked_table = Table.objects.select_for_update().select_related('table_type').get(pk=table.pk)
            if locked_table.status != Table.Status.AVAILABLE:
                raise ValidationError({
                    'initial_table': f'Table is not available (current status: {locked_table.status}).',
                })

            # Buat PlaySession
            session = PlaySession.objects.create(
                outlet_id=outlet_id,
                shift=shift,
                customer_name=customer_name,
                customer_phone=customer_phone,
                initial_table=locked_table,
                package=package,
                status=PlaySession.Status.RUNNING,
                officer_start_id=officer_start_id,
            )

            # Tentukan rate_source untuk segmen pertama
            rate_source_type, rate_snapshot = SessionService._resolve_rate_source(
                table=locked_table,
                package=package,
            )

            # Validate: no active segment for this session or table
            active_errors = SessionTableLog.validate_invariants(
                session_id=session.pk,
                table_id=locked_table.pk,
                started_at=timezone.now(),
            )
            if active_errors:
                raise ValidationError(active_errors)

            # Buat SessionTableLog pertama
            try:
                SessionTableLog.objects.create(
                    session=session,
                    table=locked_table,
                    rate_source_type=rate_source_type,
                    rate_source_snapshot=rate_snapshot,
                    started_at=timezone.now(),
                )
            except IntegrityError as e:
                raise ValidationError(
                    {'table': 'Table is already in use or session already has an active segment.'}
                ) from e

            # Set meja occupied
            locked_table.status = Table.Status.OCCUPIED
            locked_table.save(update_fields=['status'])

        return session

    # ------------------------------------------------------------------
    # Transfer Table
    # ------------------------------------------------------------------
    @staticmethod
    def transfer_table(
        *,
        session_id: int,
        new_table_id: int,
        officer_id: int,
    ) -> SessionTableLog:
        """
        Pindah meja: tutup segmen lama, buka segmen baru.

        - Validasi sesi masih running
        - Validasi meja baru available
        - Set meja lama available, meja baru occupied
        """
        try:
            session = PlaySession.objects.select_related('package').get(pk=session_id)
        except PlaySession.DoesNotExist:
            raise ValidationError({'session': 'Session does not exist.'})
        if session.status != PlaySession.Status.RUNNING:
            raise ValidationError({'session': 'Session is not running.'})

        # Validasi segmen aktif saat ini
        active_log = SessionTableLog.objects.filter(
            session_id=session_id,
            ended_at__isnull=True,
        ).select_related('table').first()
        if not active_log:
            raise ValidationError({'session': 'No active table log found for this session.'})

        old_table = active_log.table

        # Validasi meja baru (lightweight: existence + outlet only)
        try:
            new_table = Table.objects.only('id', 'outlet_id').get(pk=new_table_id)
        except Table.DoesNotExist:
            raise ValidationError({'new_table': 'Table does not exist.'})
        if new_table.outlet_id != session.outlet_id:
            raise ValidationError({'new_table': 'New table does not belong to this outlet.'})

        now = timezone.now()

        with transaction.atomic():
            # Lock + validasi availability new_table secara atomik
            locked_new_table = Table.objects.select_for_update().select_related('table_type').get(pk=new_table.pk)
            if locked_new_table.status != Table.Status.AVAILABLE:
                raise ValidationError({
                    'new_table': f'Table is not available (current status: {locked_new_table.status}).',
                })
            # Tutup segmen lama
            duration = (now - active_log.started_at).total_seconds() / 60.0
            amount = SessionService._calculate_amount(
                rate_source_type=active_log.rate_source_type,
                rate_snapshot=active_log.rate_source_snapshot,
                duration_minutes=duration,
            )
            active_log.ended_at = now
            active_log.duration_minutes = round(duration, 2)
            active_log.amount = amount
            active_log.save(update_fields=['ended_at', 'duration_minutes', 'amount'])

            # Set meja lama kembali available
            old_table.status = Table.Status.AVAILABLE
            old_table.save(update_fields=['status'])

            # Tentukan rate_source untuk segmen baru
            rate_source_type, rate_snapshot = SessionService._resolve_rate_source(
                table=locked_new_table,
                package=session.package,
            )

            # Validate: no active segment for table (session segment was just closed above)
            active_errors = SessionTableLog.validate_invariants(
                session_id=session.pk,
                table_id=locked_new_table.pk,
                started_at=now,
            )
            if active_errors:
                raise ValidationError(active_errors)

            # Buat segmen baru
            try:
                new_log = SessionTableLog.objects.create(
                    session=session,
                    table=locked_new_table,
                    rate_source_type=rate_source_type,
                    rate_source_snapshot=rate_snapshot,
                    started_at=now,
                )
            except IntegrityError as e:
                raise ValidationError(
                    {'new_table': 'Table is already in use or session already has an active segment.'}
                ) from e

            # Set meja baru occupied
            locked_new_table.status = Table.Status.OCCUPIED
            locked_new_table.save(update_fields=['status'])

        return new_log

    # ------------------------------------------------------------------
    # End / Complete Session
    # ------------------------------------------------------------------
    @staticmethod
    def end_session(
        *,
        session_id: int,
        officer_end_id: int,
    ) -> PlaySession:
        """
        Tutup sesi: tutup segmen aktif, hitung subtotal + additional fee,
        set status session completed, set meja available.
        """
        try:
            session = PlaySession.objects.select_related('outlet', 'package').get(pk=session_id)
        except PlaySession.DoesNotExist:
            raise ValidationError({'session': 'Session does not exist.'})
        if session.status != PlaySession.Status.RUNNING:
            raise ValidationError({'session': 'Session is not running.'})

        active_log = SessionTableLog.objects.filter(
            session_id=session_id,
            ended_at__isnull=True,
        ).select_related('table').first()

        now = timezone.now()

        with transaction.atomic():
            # Tutup segmen aktif jika ada
            if active_log:
                duration = (now - active_log.started_at).total_seconds() / 60.0
                amount = SessionService._calculate_amount(
                    rate_source_type=active_log.rate_source_type,
                    rate_snapshot=active_log.rate_source_snapshot,
                    duration_minutes=duration,
                )
                active_log.ended_at = now
                active_log.duration_minutes = round(duration, 2)
                active_log.amount = amount
                active_log.save(update_fields=['ended_at', 'duration_minutes', 'amount'])

                # Set meja available
                active_log.table.status = Table.Status.AVAILABLE
                active_log.table.save(update_fields=['status'])

            # Hitung subtotal dari semua table_logs
            subtotal = SessionTableLog.objects.filter(
                session_id=session_id,
            ).aggregate(
                total=models.Sum('amount'),
            )['total'] or Decimal('0.00')

            # Hitung additional fees
            additional_fee_total = SessionService._calculate_additional_fees(
                outlet_id=session.outlet_id,
                subtotal=subtotal,
            )

            total_amount = subtotal + additional_fee_total

            # Update session
            session.status = PlaySession.Status.COMPLETED
            session.ended_at = now
            session.officer_end_id = officer_end_id
            session.subtotal = subtotal
            session.additional_fee_total = additional_fee_total
            session.total_amount = total_amount
            session.save()

        return session

    # ------------------------------------------------------------------
    # Cancel Session
    # ------------------------------------------------------------------
    @staticmethod
    def cancel_session(
        *,
        session_id: int,
        officer_end_id: int,
        cancel_reason: str,
    ) -> PlaySession:
        """
        Batalkan sesi: tutup semua segmen (amount = 0), set meja available,
        set status cancelled.
        """
        try:
            session = PlaySession.objects.get(pk=session_id)
        except PlaySession.DoesNotExist:
            raise ValidationError({'session': 'Session does not exist.'})
        if session.status != PlaySession.Status.RUNNING:
            raise ValidationError({'session': 'Session is not running.'})

        now = timezone.now()

        with transaction.atomic():
            # Tutup semua segmen aktif (amount = 0, tidak ada charge)
            active_logs = SessionTableLog.objects.filter(
                session_id=session_id,
                ended_at__isnull=True,
            ).select_related('table')

            for log in active_logs:
                log.ended_at = now
                log.duration_minutes = 0
                log.amount = Decimal('0.00')
                log.save(update_fields=['ended_at', 'duration_minutes', 'amount'])

                # Set meja available
                log.table.status = Table.Status.AVAILABLE
                log.table.save(update_fields=['status'])

            # Update session
            session.status = PlaySession.Status.CANCELLED
            session.ended_at = now
            session.officer_end_id = officer_end_id
            session.subtotal = None
            session.additional_fee_total = None
            session.total_amount = None
            session.cancel_reason = cancel_reason
            session.save()

        return session

    # ------------------------------------------------------------------
    # Helper: resolve rate source
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_rate_source(
        table,
        package: Package | None = None,
    ) -> tuple[str, dict]:
        """
        Tentukan rate_source & buat snapshot berdasarkan package atau pricing rule.

        Priority:
        1. Jika ada package → package_rate (snapshot dari package)
        2. Jika tidak ada package → cari pricing rule yang cocok
        3. Fallback: default pricing rule
        """
        if package:
            return SessionTableLog.RateSourceType.PACKAGE_RATE, {
                'package_id': package.id,
                'package_name': package.name,
                'package_type': package.type,
                'fixed_price': str(package.fixed_price) if package.fixed_price else None,
                'price_per_minute': str(package.price_per_minute) if package.price_per_minute else None,
                'duration_minutes': package.duration_minutes,
            }

        # Cari pricing rule yang cocok berdasarkan waktu sekarang
        now = timezone.now().time()
        today = timezone.now().date()
        today_weekday = today.weekday()  # 0=Mon ... 6=Sun

        # Build day_type filter
        if today_weekday < 5:
            current_day_type = PricingRule.DayType.WEEKDAY
        else:
            current_day_type = PricingRule.DayType.WEEKEND

        day_type_filter = models.Q(day_type=current_day_type) | models.Q(
            day_type=PricingRule.DayType.SPECIFIC_DAY,
            specific_date=today,
        )

        rule = PricingRule.objects.filter(
            outlet_id=table.outlet_id,
            is_active=True,
            start_time__lte=now,
            end_time__gte=now,
        ).filter(
            day_type_filter,
            models.Q(table_type=table.table_type) | models.Q(table_type__isnull=True),
        ).order_by('-priority').first()

        if not rule:
            # Fallback rule (generic)
            rule = PricingRule.objects.filter(
                outlet_id=table.outlet_id,
                is_active=True,
                table_type__isnull=True,
            ).order_by('-priority').first()

        if rule:
            return SessionTableLog.RateSourceType.PRICING_RULE, {
                'pricing_rule_id': rule.id,
                'pricing_rule_name': rule.name,
                'price_per_minute': str(rule.price_per_minute),
                'day_type': rule.day_type,
                'start_time': str(rule.start_time),
                'end_time': str(rule.end_time),
                'priority': rule.priority,
            }

        # Default jika tidak ada rule sama sekali
        return SessionTableLog.RateSourceType.PRICING_RULE, {
            'pricing_rule_id': None,
            'pricing_rule_name': 'Default',
            'price_per_minute': '0.00',
            'day_type': 'weekday',
            'start_time': '00:00:00',
            'end_time': '23:59:59',
            'priority': 0,
        }

    # ------------------------------------------------------------------
    # Helper: calculate amount
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_amount(
        rate_source_type: str,
        rate_snapshot: dict,
        duration_minutes: float,
    ) -> Decimal:
        """
        Hitung biaya segmen berdasarkan rate_source.
        """
        if rate_source_type == SessionTableLog.RateSourceType.PACKAGE_RATE:
            pkg_type = rate_snapshot.get('package_type', '')
            fixed_price = Decimal(rate_snapshot.get('fixed_price', '0') or '0')
            price_per_minute = Decimal(rate_snapshot.get('price_per_minute', '0') or '0')

            if pkg_type == Package.PackageType.FIXED_DURATION:
                return fixed_price
            elif pkg_type == Package.PackageType.PER_MINUTE:
                return (Decimal(str(duration_minutes)) * price_per_minute).quantize(Decimal('0.01'))
            elif pkg_type == Package.PackageType.OPEN_LOSS:
                return Decimal('0.00')
            elif pkg_type == Package.PackageType.HAPPY_HOUR:
                return fixed_price
            else:
                return Decimal('0.00')

        elif rate_source_type == SessionTableLog.RateSourceType.PRICING_RULE:
            price_per_minute = Decimal(rate_snapshot.get('price_per_minute', '0') or '0')
            return (Decimal(str(duration_minutes)) * price_per_minute).quantize(Decimal('0.01'))

        return Decimal('0.00')

    # ------------------------------------------------------------------
    # Helper: calculate additional fees
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_additional_fees(outlet_id: int, subtotal: Decimal) -> Decimal:
        """Hitung total additional fees (service fee, tax, dll) untuk outlet."""
        fees = AdditionalFee.objects.filter(
            outlet_id=outlet_id,
            is_active=True,
        )

        total_fee = Decimal('0.00')
        for fee in fees:
            if fee.type == AdditionalFee.FeeType.PERCENTAGE:
                total_fee += (subtotal * fee.value / Decimal('100.00')).quantize(Decimal('0.01'))
            elif fee.type == AdditionalFee.FeeType.FIXED:
                total_fee += fee.value

        return total_fee