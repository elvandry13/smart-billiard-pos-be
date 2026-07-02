from rest_framework import viewsets

from users.permissions import IsAdminOrSuperAdmin


class OutletScopedViewSet(viewsets.ModelViewSet):
    """Base ViewSet that auto-scopes queryset to user's outlet (non-SuperAdmin)."""

    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_super_admin:
            return qs
        return qs.filter(outlet=user.outlet)

    def get_serializer(self, *args, **kwargs):
        user = self.request.user
        if not user.is_super_admin:
            data = kwargs.get('data')
            if data is not None:
                data = data.copy()
                data['outlet'] = user.outlet_id
                kwargs['data'] = data
        return super().get_serializer(*args, **kwargs)

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_super_admin:
            serializer.save()
        else:
            serializer.save(outlet=user.outlet)

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_super_admin:
            serializer.save()
        else:
            serializer.save(outlet=user.outlet)