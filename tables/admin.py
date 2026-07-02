from django.contrib import admin

from tables.models import TableType, Table, PricingRule, AdditionalFee


@admin.register(TableType)
class TableTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'outlet', 'created_at']
    list_filter = ['outlet']
    search_fields = ['name']


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ['name', 'outlet', 'table_type', 'status', 'updated_at']
    list_filter = ['outlet', 'status', 'table_type']
    search_fields = ['name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = ['name', 'outlet', 'table_type', 'day_type', 'price_per_minute', 'priority', 'is_active']
    list_filter = ['outlet', 'day_type', 'is_active']
    search_fields = ['name']


@admin.register(AdditionalFee)
class AdditionalFeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'outlet', 'type', 'value', 'is_active']
    list_filter = ['outlet', 'type', 'is_active']
    search_fields = ['name']