from rest_framework import serializers


class DashboardSummarySerializer(serializers.Serializer):
    """Response for GET /api/dashboard/summary/"""
    total_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    total_sessions = serializers.IntegerField()
    avg_duration_minutes = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )
    avg_revenue_per_session = serializers.DecimalField(
        max_digits=14, decimal_places=2, allow_null=True,
    )
    most_used_package = serializers.DictField(allow_null=True)


class DashboardSummaryRequestSerializer(serializers.Serializer):
    """Query params for dashboard summary."""
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)


class RevenueTrendItemSerializer(serializers.Serializer):
    """Single data point in revenue-trend response."""
    date = serializers.DateField()
    revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    session_count = serializers.IntegerField()


class DashboardRevenueTrendSerializer(serializers.Serializer):
    """Response for GET /api/dashboard/revenue-trend/"""
    granularity = serializers.ChoiceField(choices=['daily', 'weekly'])
    data = RevenueTrendItemSerializer(many=True)


class DashboardTrendRequestSerializer(serializers.Serializer):
    """Query params for revenue trend."""
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    granularity = serializers.ChoiceField(
        choices=['daily', 'weekly'], default='daily',
    )


class TopCustomerItemSerializer(serializers.Serializer):
    """Single customer in top-customers response."""
    customer_phone = serializers.CharField()
    customer_name = serializers.CharField()
    visit_count = serializers.IntegerField()
    total_spend = serializers.DecimalField(max_digits=14, decimal_places=2)


class DashboardTopCustomersSerializer(serializers.Serializer):
    """Response for GET /api/dashboard/top-customers/"""
    data = TopCustomerItemSerializer(many=True)


class TopCustomersRequestSerializer(serializers.Serializer):
    """Query params for top customers."""
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    limit = serializers.IntegerField(default=10, min_value=1, max_value=50)