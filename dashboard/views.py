from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from users.models import Outlet
from dashboard.permissions import IsOwnerOrAdmin
from dashboard.serializers import (
    DashboardSummarySerializer,
    DashboardSummaryRequestSerializer,
    DashboardRevenueTrendSerializer,
    DashboardTrendRequestSerializer,
    DashboardTopCustomersSerializer,
    TopCustomersRequestSerializer,
)
from dashboard.services import DashboardService


class DashboardViewSet(viewsets.GenericViewSet):
    """
    ViewSet untuk dashboard analytics.
    """

    permission_classes = [IsOwnerOrAdmin]

    def _get_outlet_ids(self):
        """Resolve outlet scope based on user role."""
        user = self.request.user
        if user.is_owner:
            # All outlets in the user's tenant
            return list(
                Outlet.objects.filter(tenant=user.tenant).values_list('id', flat=True)
            )
        elif user.is_admin:
            # Only admin's own outlet
            return [user.outlet_id]
        return []

    # ------------------------------------------------------------------
    # GET /api/dashboard/summary/
    # ------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='summary')
    def summary(self, request):
        """Aggregated summary metrics."""
        query_serializer = DashboardSummaryRequestSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        qd = query_serializer.validated_data

        outlet_ids = self._get_outlet_ids()
        data = DashboardService.get_summary(
            outlet_ids=outlet_ids,
            date_from=qd.get('date_from'),
            date_to=qd.get('date_to'),
        )

        output_serializer = DashboardSummarySerializer(data)
        return Response(output_serializer.data)

    # ------------------------------------------------------------------
    # GET /api/dashboard/revenue-trend/
    # ------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='revenue-trend')
    def revenue_trend(self, request):
        """Revenue trend over time (daily/weekly)."""
        query_serializer = DashboardTrendRequestSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        qd = query_serializer.validated_data

        outlet_ids = self._get_outlet_ids()
        granularity, data = DashboardService.get_revenue_trend(
            outlet_ids=outlet_ids,
            date_from=qd.get('date_from'),
            date_to=qd.get('date_to'),
            granularity=qd.get('granularity', 'daily'),
        )

        output_serializer = DashboardRevenueTrendSerializer({
            'granularity': granularity,
            'data': data,
        })
        return Response(output_serializer.data)

    # ------------------------------------------------------------------
    # GET /api/dashboard/top-customers/
    # ------------------------------------------------------------------
    @action(detail=False, methods=['get'], url_path='top-customers')
    def top_customers(self, request):
        """Top customers by total spend."""
        query_serializer = TopCustomersRequestSerializer(data=request.query_params)
        query_serializer.is_valid(raise_exception=True)
        qd = query_serializer.validated_data

        outlet_ids = self._get_outlet_ids()
        data = DashboardService.get_top_customers(
            outlet_ids=outlet_ids,
            date_from=qd.get('date_from'),
            date_to=qd.get('date_to'),
            limit=qd.get('limit', 10),
        )

        output_serializer = DashboardTopCustomersSerializer({'data': data})
        return Response(output_serializer.data)