from django.contrib import admin

from shifts.models import Shift


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ['id', 'outlet', 'officer', 'status', 'opening_cash', 'expected_cash', 'difference', 'opened_at', 'closed_at']
    list_filter = ['status', 'outlet']
    search_fields = ['officer__username']
    readonly_fields = ['expected_cash', 'difference', 'opened_at', 'closed_at']