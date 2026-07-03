from rest_framework import mixins, viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from users.permissions import IsAdminOrSuperAdmin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """ViewSet read-only untuk AuditLog — hanya Admin & Super Admin."""

    queryset = AuditLog.objects.select_related('user', 'outlet').all()
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdminOrSuperAdmin]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['action', 'object_type', 'user']
    search_fields = ['object_type', 'notes']
    ordering_fields = ['created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_super_admin:
            return qs

        # Admin hanya lihat audit log outlet-nya
        if user.is_admin:
            return qs.filter(outlet=user.outlet)

        return qs.none()