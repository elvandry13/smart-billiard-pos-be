from rest_framework import permissions


class IsSuperAdmin(permissions.BasePermission):
    """Hanya Super Admin yang bisa akses."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_super_admin


class IsOwner(permissions.BasePermission):
    """Hanya Owner yang bisa akses."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_owner


class IsAdmin(permissions.BasePermission):
    """Hanya Admin yang bisa akses."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin


class IsOfficer(permissions.BasePermission):
    """Hanya Officer yang bisa akses."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_officer


class IsAdminOrOfficer(permissions.BasePermission):
    """Admin atau Officer di outlet yang sama."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_admin or request.user.is_officer)


class IsSuperAdminOrOwner(permissions.BasePermission):
    """Super Admin atau Owner."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_super_admin or request.user.is_owner)


class HasRolePermission(permissions.BasePermission):
    """
    Permission berbasis Role + Permission dari model custom.
    Mengecek apakah user memiliki permission dengan codename tertentu.
    Gunakan di view dengan attribute `required_permission`.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        required = getattr(view, 'required_permission', None)
        if required is None:
            return True
        # Super Admin auto-all
        if request.user.is_super_admin:
            return True
        # Cek via Role -> Permission
        user_roles = request.user.roles.all()
        return user_roles.filter(permissions__codename=required).exists()


class IsAdminOrSuperAdminOrOwner(permissions.BasePermission):
    """Super Admin, Owner (read), atau Admin bisa akses list/retrieve."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.is_super_admin:
            return True
        if request.user.is_owner and view.action in ['list', 'retrieve']:
            return True
        if request.user.is_admin:
            return True
        return False


class IsAdminOrSuperAdmin(permissions.BasePermission):
    """Super Admin atau Admin (write operations)."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and (request.user.is_super_admin or request.user.is_admin)


class TenantOutletScoping(permissions.BasePermission):
    """
    Row-level scoping: memastikan user non-Super-Admin hanya bisa
    mengakses data di outlet/tenant miliknya.

    View harus menyediakan metode `get_outlet_filter()` atau
    `get_tenant_filter()` yang mengembalikan dict filter queryset.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_super_admin:
            return True
        outlet_id = getattr(obj, 'outlet_id', None)
        if outlet_id and request.user.outlet_id:
            return outlet_id == request.user.outlet_id
        tenant_id = getattr(obj, 'tenant_id', None)
        if tenant_id and request.user.tenant_id:
            return tenant_id == request.user.tenant_id
        return False