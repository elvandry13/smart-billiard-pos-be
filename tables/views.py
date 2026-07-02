from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from tables.models import TableType, Table, PricingRule, AdditionalFee
from tables.serializers import (
    TableTypeSerializer,
    TableSerializer,
    PricingRuleSerializer,
    AdditionalFeeSerializer,
)
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


class TableTypeViewSet(OutletScopedViewSet):
    queryset = TableType.objects.all()
    serializer_class = TableTypeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['name']
    search_fields = ['name']


class TableViewSet(OutletScopedViewSet):
    queryset = Table.objects.select_related('table_type').all()
    serializer_class = TableSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['table_type', 'status']
    search_fields = ['name']


class PricingRuleViewSet(OutletScopedViewSet):
    queryset = PricingRule.objects.select_related('table_type').all()
    serializer_class = PricingRuleSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['table_type', 'day_type', 'is_active']
    search_fields = ['name']


class AdditionalFeeViewSet(OutletScopedViewSet):
    queryset = AdditionalFee.objects.all()
    serializer_class = AdditionalFeeSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'is_active']
    search_fields = ['name']