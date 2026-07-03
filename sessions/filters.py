from django_filters import rest_framework as filters

from .models import PlaySession


class SessionFilter(filters.FilterSet):
    """Custom filter untuk PlaySession dengan dukungan partial-match customer_phone."""
    customer_phone = filters.CharFilter(lookup_expr='icontains')
    # Additional: date range filtering via started_at
    started_at_after = filters.DateTimeFilter(field_name='started_at', lookup_expr='gte')
    started_at_before = filters.DateTimeFilter(field_name='started_at', lookup_expr='lte')

    class Meta:
        model = PlaySession
        fields = ['status', 'outlet', 'shift', 'package',
                   'customer_phone', 'started_at_after', 'started_at_before']