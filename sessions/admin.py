from django.contrib import admin

from .models import PlaySession, SessionTableLog


class SessionTableLogInline(admin.TabularInline):
    model = SessionTableLog
    extra = 0
    readonly_fields = [
        'table', 'rate_source_type', 'rate_source_snapshot',
        'started_at', 'ended_at', 'duration_minutes', 'amount',
    ]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PlaySession)
class PlaySessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'outlet', 'customer_name', 'initial_table', 'package',
        'status', 'started_at', 'ended_at', 'total_amount',
    ]
    list_filter = ['status', 'outlet', 'shift']
    search_fields = ['customer_name', 'customer_phone']
    readonly_fields = [
        'subtotal', 'additional_fee_total', 'total_amount',
        'started_at', 'ended_at', 'created_at',
    ]
    inlines = [SessionTableLogInline]
    fieldsets = (
        (None, {
            'fields': (
                'outlet', 'shift', 'customer_name', 'customer_phone',
                'initial_table', 'package', 'status',
            ),
        }),
        ('Officers', {
            'fields': ('officer_start', 'officer_end'),
        }),
        ('Financial', {
            'fields': ('subtotal', 'additional_fee_total', 'total_amount'),
        }),
        ('Timestamps', {
            'fields': ('started_at', 'ended_at', 'created_at'),
        }),
        ('Cancellation', {
            'fields': ('cancel_reason',),
        }),
    )


@admin.register(SessionTableLog)
class SessionTableLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session', 'table', 'rate_source_type',
        'started_at', 'ended_at', 'duration_minutes', 'amount',
    ]
    list_filter = ['rate_source_type']
    search_fields = ['session__customer_name']
    readonly_fields = [
        'session', 'table', 'rate_source_type', 'rate_source_snapshot',
        'started_at', 'ended_at', 'duration_minutes', 'amount',
    ]