from django.db import transaction
from rest_framework import viewsets

from users.permissions import IsAdminOrSuperAdmin
from audit_logs.services import AuditService


class OutletScopedViewSet(viewsets.ModelViewSet):
    """Base ViewSet that auto-scopes queryset to user's outlet (non-SuperAdmin)."""

    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, 'swagger_fake_view', False):
            return qs
        user = self.request.user
        if user.is_super_admin:
            return qs
        return qs.filter(outlet=user.outlet)

    def get_serializer(self, *args, **kwargs):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_serializer(*args, **kwargs)
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
            obj = serializer.save()
        else:
            obj = serializer.save(outlet=user.outlet)

        # Tentukan action name dari model class
        model_name = self.queryset.model.__name__
        action = f'create_{model_name.lower()}'
        outlet_id = getattr(obj, 'outlet_id', None)
        AuditService.log(
            user_id=user.id,
            outlet_id=outlet_id,
            action=action,
            object_type=model_name,
            object_id=obj.id,
        )

    def perform_update(self, serializer):
        user = self.request.user
        if user.is_super_admin:
            obj = serializer.save()
        else:
            obj = serializer.save(outlet=user.outlet)

        model_name = self.queryset.model.__name__
        action = f'update_{model_name.lower()}'
        outlet_id = getattr(obj, 'outlet_id', None)
        AuditService.log(
            user_id=user.id,
            outlet_id=outlet_id,
            action=action,
            object_type=model_name,
            object_id=obj.id,
        )

    def perform_destroy(self, instance):
        model_name = self.queryset.model.__name__
        action = f'delete_{model_name.lower()}'
        obj_id = instance.id
        outlet_id = getattr(instance, 'outlet_id', None)
        with transaction.atomic():
            instance.delete()
            AuditService.log(
                user_id=self.request.user.id,
                outlet_id=outlet_id,
                action=action,
                object_type=model_name,
                object_id=obj_id,
            )
