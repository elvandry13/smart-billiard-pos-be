from django.contrib import admin

from payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session', 'method', 'status', 'amount', 'paid_at', 'created_by',
    ]
    list_filter = ['method', 'status', 'paid_at']
    search_fields = ['session__customer_name', 'session__customer_phone']
    readonly_fields = ['paid_at', 'created_at']