from django.core.exceptions import ValidationError
from django.db import transaction

from payments.models import Payment
from sessions.models import PlaySession
from users.models import User


class PaymentService:
    """Service layer untuk pembuatan pembayaran."""

    @staticmethod
    @transaction.atomic
    def create_payment(
        *,
        session_id: int,
        outlet_id: int,
        method: str,
        amount,
        created_by_id: int,
        gateway_reference: str = '',
    ) -> Payment:
        session = PlaySession.objects.select_for_update().filter(
            id=session_id, outlet_id=outlet_id,
        ).first()

        if session is None:
            raise ValidationError({'session': 'Session not found.'})

        if session.status != PlaySession.Status.COMPLETED:
            raise ValidationError({'session': 'Payment is only allowed for completed sessions.'})

        if session.total_amount is None:
            raise ValidationError({'session': 'Session total amount is not yet calculated.'})

        if amount != session.total_amount:
            raise ValidationError({
                'amount': f'Amount must match session total ({session.total_amount}).',
            })

        # Cek sudah ada payment paid untuk session ini
        existing = Payment.objects.filter(
            session=session, status=Payment.Status.PAID,
        ).exists()
        if existing:
            raise ValidationError({'session': 'This session already has a paid payment.'})

        created_by = User.objects.get(id=created_by_id)
        payment = Payment.objects.create(
            session=session,
            method=method,
            status=Payment.Status.PAID,
            amount=amount,
            gateway_reference=gateway_reference,
            created_by=created_by,
        )
        return payment