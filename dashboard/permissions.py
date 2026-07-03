from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Owner: full dashboard access across all outlets in their tenant.
    Admin: summary + revenue-trend for own outlet only. top-customers blocked.
    Super Admin + Officer: denied.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        if user.is_super_admin:
            return False

        if user.is_owner:
            return True

        if user.is_admin:
            # Admin cannot access top_customers
            if view.action == 'top_customers':
                return False
            return True

        return False