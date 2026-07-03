from django.db import models


class InvoiceSequence(models.Model):
    """Counter invoice number per outlet per hari."""

    outlet = models.ForeignKey(
        'users.Outlet',
        on_delete=models.CASCADE,
        related_name='invoice_sequences',
    )
    last_sequence = models.IntegerField(default=0)
    date = models.DateField()

    class Meta:
        unique_together = ('outlet', 'date')
        verbose_name = 'Invoice Sequence'
        verbose_name_plural = 'Invoice Sequences'

    def __str__(self):
        return f'{self.outlet.code} - {self.date} - {self.last_sequence:04d}'


class Receipt(models.Model):
    """Struk PDF yang dihasilkan setelah pembayaran sukses."""

    session = models.ForeignKey(
        'play_sessions.PlaySession',
        on_delete=models.PROTECT,
        related_name='receipts',
    )
    invoice_number = models.CharField(max_length=50, unique=True)
    pdf_file = models.FileField(upload_to='receipts/%Y/%m/')
    printed_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='receipts_printed',
    )
    printed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['printed_by']),
            models.Index(fields=['printed_at']),
        ]
        verbose_name = 'Receipt'
        verbose_name_plural = 'Receipts'
        ordering = ['-printed_at']

    def __str__(self):
        return f'Receipt {self.invoice_number} — Session {self.session_id}'