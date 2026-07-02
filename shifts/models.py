from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from users.models import Outlet, User


class Shift(models.Model):
    """Shift officer — mencatat buka-tutup shift dan rekonsiliasi kas."""

    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        CLOSED = 'closed', 'Closed'

    outlet = models.ForeignKey(
        Outlet, on_delete=models.PROTECT, related_name='shifts',
    )
    officer = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='shifts',
    )
    opening_cash = models.DecimalField(max_digits=12, decimal_places=2)
    closing_cash = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
    )
    expected_cash = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='opening_cash + total cash payment selama shift (dihitung sistem saat tutup)',
    )
    difference = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='closing_cash - expected_cash',
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.OPEN,
    )
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-opened_at']
        unique_together = ['outlet', 'officer', 'opened_at']

    def __str__(self):
        return f"Shift #{self.id} — {self.officer.username} ({self.status})"

    @staticmethod
    def validate_invariants(
        *,
        status,
        opening_cash=None,
        closing_cash=None,
        expected_cash=None,
        difference=None,
        officer_id=None,
        outlet_id=None,
        exclude_pk=None,
    ):
        """
        Validasi aturan bisnis Shift. Return dict errors (empty jika valid).
        Dipanggil dari clean() dan serializer.
        """
        errors = {}

        if opening_cash is not None and opening_cash <= 0:
            errors['opening_cash'] = 'Opening cash must be greater than 0.'

        if status == Shift.Status.OPEN:
            if closing_cash is not None:
                errors['closing_cash'] = 'Closing cash must be null while shift is open.'
            if expected_cash is not None:
                errors['expected_cash'] = 'Expected cash must be null while shift is open.'
            if difference is not None:
                errors['difference'] = 'Difference must be null while shift is open.'

        elif status == Shift.Status.CLOSED:
            if closing_cash is None:
                errors['closing_cash'] = 'Closing cash is required when closing shift.'

        # Satu officer hanya boleh punya satu shift open
        if status == Shift.Status.OPEN and officer_id and outlet_id:
            existing = Shift.objects.filter(
                officer_id=officer_id,
                outlet_id=outlet_id,
                status=Shift.Status.OPEN,
            )
            if exclude_pk is not None:
                existing = existing.exclude(pk=exclude_pk)
            if existing.exists():
                errors['officer'] = 'Officer already has an open shift in this outlet.'

        return errors

    def clean(self):
        super().clean()
        errors = self.validate_invariants(
            status=self.status,
            opening_cash=self.opening_cash,
            closing_cash=self.closing_cash,
            expected_cash=self.expected_cash,
            difference=self.difference,
            officer_id=self.officer_id,
            outlet_id=self.outlet_id,
            exclude_pk=self.pk,
        )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_status = None if is_new else Shift.objects.only('status').get(pk=self.pk).status

        if not is_new and old_status == self.Status.OPEN and self.status == self.Status.CLOSED:
            # Hitung expected_cash = opening_cash (belum ada payment cash di Fase 4)
            if self.expected_cash is None:
                self.expected_cash = self.opening_cash or 0
            if self.closed_at is None:
                self.closed_at = timezone.now()
            if self.difference is None and self.closing_cash is not None:
                self.difference = self.closing_cash - self.expected_cash

        super().save(*args, **kwargs)
