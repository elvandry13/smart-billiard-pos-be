from django.contrib import admin

from receipts.models import InvoiceSequence, Receipt


@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(admin.ModelAdmin):
    list_display = ['outlet', 'date', 'last_sequence']
    list_filter = ['outlet', 'date']
    search_fields = ['outlet__name', 'outlet__code']
    readonly_fields = ['outlet', 'date']


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'session', 'printed_by', 'printed_at']
    list_filter = ['printed_at']
    search_fields = ['invoice_number', 'session__customer_name']
    readonly_fields = [
        'invoice_number',
        'session',
        'pdf_file',
        'printed_by',
        'printed_at',
        'created_at',
    ]
    ordering = ['-printed_at']