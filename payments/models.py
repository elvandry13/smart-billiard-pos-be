from django.core.exceptions import ValidationError
from django.db import models

from sessions.models import PlaySession
from users.models import User


class Payment(models.Model):
    """Pencatatan pembayaran untuk satu sesi bermain."""

    class Method(models.TextChoices):
        CASH = 'cash', 'Cash'
        QRIS = 'qris', 'QRIS'
        E_WALLET = 'e_wallet', 'E-Wallet'
        CARD = 'card', 'Card'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'

    session = models.ForeignKey(
        PlaySession,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    method = models.CharField(
        max_length=20,
        choices=Method.choices,
        default=Method.CASH,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PAID,
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    gateway_reference = models.CharField(
        max_length=255, blank=True, default='',
    )
    paid_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='payments_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at']
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['created_by']),
            models.Index(fields=['paid_at']),
        ]

    def __str__(self):
        return f"#{self.id} — {self.session} ({self.get_method_display()})"

    def clean(self):
        super().clean()
        errors = {}

        if self.session and self.session.status != PlaySession.Status.COMPLETED:
            errors['session'] = 'Payment is only allowed for completed sessions.'

        if self.status == self.Status.PAID and self.session and self.session.total_amount is not None:
            if self.amount != self.session.total_amount:
                errors['amount'] = (
                    f'Amount must match the session total amount '
                    f'({self.session.total_amount}).'
                )

        if errors:
            raise ValidationError(errors)