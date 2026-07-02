from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend

from core.views import OutletScopedViewSet
from packages.models import Package
from packages.serializers import PackageSerializer


class PackageViewSet(OutletScopedViewSet):
    queryset = Package.objects.all()
    serializer_class = PackageSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'valid_day_type', 'is_active']
    search_fields = ['name']
    ordering_fields = ['name', 'created_at', 'updated_at']