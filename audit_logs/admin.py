from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'action', 'object_type', 'object_id', 'user', 'outlet', 'created_at']
    list_filter = ['action', 'object_type', 'created_at']
    search_fields = ['object_type', 'notes', 'user__username']
    readonly_fields = [f.name for f in AuditLog._meta.fields]