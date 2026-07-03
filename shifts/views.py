from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from shifts.models import Shift
from shifts.serializers import ShiftSerializer
from users.permissions import IsOfficerOrSuperAdmin
from audit_logs.services import AuditService


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.select_related('outlet', 'officer').all()
    serializer_class = ShiftSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'officer']
    search_fields = ['officer__username', 'notes']
    ordering_fields = ['opened_at', 'closed_at']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsOfficerOrSuperAdmin()]

    def get_serializer(self, *args, **kwargs):
        """Inject outlet & officer ke data untuk non-super-admin sebelum validasi."""
        user = self.request.user
        if not user.is_super_admin:
            data = kwargs.get('data')
            if data is not None:
                data = data.copy()
                data['outlet'] = user.outlet_id
                data['officer'] = user.id
                kwargs['data'] = data
        return super().get_serializer(*args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Super Admin — lihat semua
        if user.is_super_admin:
            return qs

        # Admin — lihat semua shift di outlet-nya
        if user.is_admin:
            return qs.filter(outlet=user.outlet)

        # Officer — hanya shift milik sendiri
        if user.is_officer:
            return qs.filter(officer=user)

        return qs.none()

    def perform_create(self, serializer):
        user = self.request.user
        # Super admin passes outlet+officer explicitly; officer auto-assigned.
        if user.is_super_admin:
            shift = serializer.save()
        else:
            shift = serializer.save(
                officer=user,
                outlet=user.outlet,
            )
        AuditService.log(
            user_id=user.id,
            outlet_id=shift.outlet_id,
            action='open_shift',
            object_type='Shift',
            object_id=shift.id,
            changes={'status': shift.status},
        )

    def perform_update(self, serializer):
        shift = serializer.save()
        AuditService.log(
            user_id=self.request.user.id,
            outlet_id=shift.outlet_id,
            action='update_shift',
            object_type='Shift',
            object_id=shift.id,
            changes={'status': shift.status},
        )

    def perform_destroy(self, instance):
        shift_id = instance.id
        outlet_id = instance.outlet_id
        instance.delete()
        AuditService.log(
            user_id=self.request.user.id,
            outlet_id=outlet_id,
            action='delete_shift',
            object_type='Shift',
            object_id=shift_id,
        )
