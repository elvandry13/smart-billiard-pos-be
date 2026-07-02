from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Tenant, Outlet, Role, Permission


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(Outlet)
class OutletAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'tenant', 'timezone', 'is_active', 'created_at']
    list_filter = ['tenant', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    filter_horizontal = ['permissions']


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'codename', 'created_at']
    search_fields = ['name', 'codename']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'email', 'role', 'tenant', 'outlet', 'is_active', 'is_staff']
    list_filter = ['role', 'tenant', 'is_active', 'is_staff']
    search_fields = ['username', 'email', 'phone']
    ordering = ['username']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email', 'phone')}),
        ('Role & Scope', {'fields': ('role', 'tenant', 'outlet', 'roles')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'created_at', 'updated_at')}),
    )
    readonly_fields = ['date_joined', 'created_at', 'updated_at']

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        ('Role & Scope', {'fields': ('role', 'tenant', 'outlet', 'roles')}),
    )

    filter_horizontal = ['roles', 'groups', 'user_permissions']