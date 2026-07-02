from django.contrib import admin

from packages.models import Package


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'outlet', 'type', 'is_active', 'created_at']
    list_filter = ['type', 'is_active', 'outlet']
    search_fields = ['name']