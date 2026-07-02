from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from tables.models import Table
from packages.models import Package
from shifts.models import Shift
from users.models import Outlet, User


class PlaySession(models.Model):
    """Sesi bermain billiard — mencatat seluruh siklus hidup satu permainan."""

    class Status(models.TextChoices):
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'

    outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name='play_sessions',
    )
    shift = models.ForeignKey(
        Shift, on_delete=models.PROTECT, related_name='play_sessions',
        help_text='Shift aktif officer saat sesi dibuka.',
    )
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20, blank=True, default='')
    initial_table = models.ForeignKey(
        Table, on_delete=models.PROTECT, related_name='play_sessions',
        help_text='Meja pertama saat sesi dibuka.',
    )
    package = models.ForeignKey(
        Package, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='play_sessions',
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.RUNNING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    officer_start = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='sessions_started',
    )
    officer_end = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sessions_ended',
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Total biaya permainan (sum table_log amounts atau fixed_price package).',
    )
    additional_fee_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    total_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    cancel_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['outlet', 'status']),
            models.Index(fields=['started_at']),
        ]

    def __str__(self):
        return f"Session #{self.id} — {self.customer_name} ({self.get_status_display()})"

    @staticmethod
    def validate_invariants(
        *,
        status,
        outlet_id=None,
        shift_id=None,
        package_id=None,
        initial_table_id=None,
        subtotal=None,
        additional_fee_total=None,
        total_amount=None,
        ended_at=None,
        cancel_reason='',
        exclude_pk=None,
    ):
        """
        Validasi aturan bisnis PlaySession. Return dict errors (empty jika valid).
        Dipanggil dari clean() dan serializer.
        """
        errors = {}

        # --- Status-specific validation ---
        if status == PlaySession.Status.COMPLETED:
            if ended_at is None:
                errors['ended_at'] = 'Ended at is required when session is completed.'
            if subtotal is None:
                errors['subtotal'] = 'Subtotal is required when session is completed.'
            if additional_fee_total is None:
                errors['additional_fee_total'] = 'Additional fee total is required when session is completed.'
            if total_amount is None:
                errors['total_amount'] = 'Total amount is required when session is completed.'

        elif status == PlaySession.Status.CANCELLED:
            if ended_at is None:
                errors['ended_at'] = 'Ended at is required when session is cancelled.'
            if not cancel_reason:
                errors['cancel_reason'] = 'Cancel reason is required when cancelling a session.'
            if subtotal is not None:
                errors['subtotal'] = 'Subtotal must be null for cancelled sessions.'
            if additional_fee_total is not None:
                errors['additional_fee_total'] = 'Additional fee total must be null for cancelled sessions.'
            if total_amount is not None:
                errors['total_amount'] = 'Total amount must be null for cancelled sessions.'

        # --- Package must belong to the same outlet ---
        if package_id and outlet_id:
            try:
                pkg = Package.objects.only('outlet_id').get(pk=package_id)
                if pkg.outlet_id != outlet_id:
                    errors['package'] = 'Package must belong to the same outlet as the session.'
            except Package.DoesNotExist:
                errors['package'] = 'Package does not exist.'

        # --- Initial table must belong to the same outlet ---
        if initial_table_id and outlet_id:
            try:
                tbl = Table.objects.only('outlet_id').get(pk=initial_table_id)
                if tbl.outlet_id != outlet_id:
                    errors['initial_table'] = 'Initial table must belong to the same outlet as the session.'
            except Table.DoesNotExist:
                errors['initial_table'] = 'Table does not exist.'

        # --- Shift must belong to the same outlet ---
        if shift_id and outlet_id:
            try:
                sft = Shift.objects.only('outlet_id', 'status', 'officer_id').get(pk=shift_id)
                if sft.outlet_id != outlet_id:
                    errors['shift'] = 'Shift must belong to the same outlet as the session.'
            except Shift.DoesNotExist:
                errors['shift'] = 'Shift does not exist.'

        return errors

    def clean(self):
        super().clean()
        errors = self.validate_invariants(
            status=self.status,
            outlet_id=self.outlet_id,
            shift_id=self.shift_id,
            package_id=self.package_id,
            initial_table_id=self.initial_table_id,
            subtotal=self.subtotal,
            additional_fee_total=self.additional_fee_total,
            total_amount=self.total_amount,
            ended_at=self.ended_at,
            cancel_reason=self.cancel_reason,
            exclude_pk=self.pk,
        )
        if errors:
            raise ValidationError(errors)


class SessionTableLog(models.Model):
    """Log per segmen meja dalam satu sesi — mendukung transfer table & multi-pricing."""

    class RateSourceType(models.TextChoices):
        PRICING_RULE = 'pricing_rule', 'Pricing Rule'
        PACKAGE_RATE = 'package_rate', 'Package Rate'

    session = models.ForeignKey(
        PlaySession, on_delete=models.CASCADE, related_name='table_logs',
    )
    table = models.ForeignKey(
        Table, on_delete=models.PROTECT, related_name='session_logs',
    )
    rate_source_type = models.CharField(
        max_length=20, choices=RateSourceType.choices,
    )
    rate_source_snapshot = models.JSONField(
        help_text='Salinan tarif yang berlaku saat segmen ini berjalan.',
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )

    class Meta:
        ordering = ['started_at']
        indexes = [
            models.Index(fields=['session', 'ended_at']),
            models.Index(fields=['table', 'ended_at']),
        ]

    def __str__(self):
        return f"TableLog #{self.id} — Session #{self.session_id} — Table {self.table_id}"

    @staticmethod
    def validate_invariants(
        *,
        started_at=None,
        ended_at=None,
        duration_minutes=None,
        amount=None,
        session_id=None,
        table_id=None,
        exclude_pk=None,
    ):
        """Validasi aturan bisnis SessionTableLog."""
        errors = {}

        if started_at and ended_at and started_at >= ended_at:
            errors['ended_at'] = 'Ended at must be after started at.'

        if ended_at is not None and duration_minutes is None:
            errors['duration_minutes'] = 'Duration is required when segment is closed.'

        if ended_at is not None and amount is None:
            errors['amount'] = 'Amount is required when segment is closed.'

        # Satu table tidak boleh dipakai di dua segmen aktif bersamaan
        if ended_at is None and table_id is not None:
            conflicting = SessionTableLog.objects.filter(
                table_id=table_id,
                ended_at__isnull=True,
            )
            if exclude_pk is not None:
                conflicting = conflicting.exclude(pk=exclude_pk)
            if conflicting.exists():
                errors['table'] = 'Table is already in use by another active session segment.'

        # Hanya boleh satu segmen aktif per sesi
        if ended_at is None and session_id is not None:
            active_segments = SessionTableLog.objects.filter(
                session_id=session_id,
                ended_at__isnull=True,
            )
            if exclude_pk is not None:
                active_segments = active_segments.exclude(pk=exclude_pk)
            if active_segments.exists():
                errors['session'] = 'Session already has an active segment. Close the current segment first.'

        return errors

    def clean(self):
        super().clean()
        errors = self.validate_invariants(
            started_at=self.started_at,
            ended_at=self.ended_at,
            duration_minutes=self.duration_minutes,
            amount=self.amount,
            session_id=self.session_id,
            table_id=self.table_id,
            exclude_pk=self.pk,
        )
        if errors:
            raise ValidationError(errors)