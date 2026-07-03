"""Business logic untuk Receipt module."""
from datetime import date

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from receipts.models import InvoiceSequence, Receipt
from receipts.pdf_generator import generate_receipt_pdf
from sessions.models import PlaySession


class ReceiptService:
    """Service class untuk operasi Receipt."""

    @staticmethod
    def generate_invoice_number(outlet) -> str:
        """
        Generate invoice number unik per outlet per hari.

        Format: {OUTLET_CODE}-{YYYYMMDD}-{sequence:04d}
        """
        today = date.today()
        seq, _created = InvoiceSequence.objects.select_for_update().get_or_create(
            outlet=outlet,
            date=today,
            defaults={'last_sequence': 0},
        )

        if seq.date != today:
            seq.date = today
            seq.last_sequence = 0

        seq.last_sequence += 1
        seq.save(update_fields=['last_sequence', 'date'])

        date_part = today.strftime('%Y%m%d')
        return f'{outlet.code}-{date_part}-{seq.last_sequence:04d}'

    @staticmethod
    def create_receipt(*, session_id: int, user_id: int) -> Receipt:
        """
        Buat receipt PDF untuk session yang sudah paid.

        Args:
            session_id: PlaySession ID yang sudah completed & paid.
            user_id: User yang mencetak receipt.

        Returns:
            Receipt instance.

        Raises:
            ValidationError jika session tidak valid atau belum paid.
        """
        from users.models import User

        try:
            session = PlaySession.objects.select_related(
                'outlet',
                'initial_table',
            ).get(pk=session_id)
        except PlaySession.DoesNotExist:
            raise ValidationError({'session': 'Session does not exist.'})

        if session.status != PlaySession.Status.COMPLETED:
            raise ValidationError(
                {'session': 'Session must be completed before generating receipt.'},
            )

        # Pastikan session sudah paid
        if not session.payments.filter(status='paid').exists():
            raise ValidationError(
                {'session': 'Session must be paid before generating receipt.'},
            )

        try:
            printed_by = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise ValidationError({'user_id': 'User does not exist.'})

        with transaction.atomic():
            invoice_number = ReceiptService.generate_invoice_number(session.outlet)

            receipt = Receipt(
                session=session,
                invoice_number=invoice_number,
                printed_by=printed_by,
            )

            # Generate PDF
            pdf_bytes = generate_receipt_pdf(session, receipt)
            date_part = timezone.now().strftime('%Y/%m')
            filename = f'receipts/{date_part}/{invoice_number}.pdf'
            receipt.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
            receipt.save()

        return receipt