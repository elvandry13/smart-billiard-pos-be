from datetime import date, timedelta
from decimal import Decimal

from django.db import models
from django.db.models.functions import TruncDate, TruncWeek

from sessions.models import PlaySession


class DashboardService:
    """Service layer untuk aggregasi data dashboard."""

    @staticmethod
    def _build_base_qs(outlet_ids: list[int], date_from: date | None, date_to: date | None):
        """Build base queryset for dashboard aggregations."""
        qs = PlaySession.objects.filter(
            outlet_id__in=outlet_ids,
            status=PlaySession.Status.COMPLETED,
            total_amount__isnull=False,
        )
        if date_from:
            qs = qs.filter(started_at__gte=date_from)
        if date_to:
            qs = qs.filter(started_at__lt=date_to + timedelta(days=1))
        return qs

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    @staticmethod
    def get_summary(
        outlet_ids: list[int],
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> dict:
        """
        Aggregate summary metrics: total_revenue, total_sessions,
        avg_duration_minutes, avg_revenue_per_session, most_used_package.
        """
        base_qs = DashboardService._build_base_qs(outlet_ids, date_from, date_to)

        agg = base_qs.aggregate(
            total_revenue=models.Sum('total_amount'),
            total_sessions=models.Count('id'),
        )
        total_revenue = agg['total_revenue'] or Decimal('0.00')
        total_sessions = agg['total_sessions']

        # Avg duration per session (sum of all table_log duration_minutes per session)
        avg_duration = None
        if total_sessions > 0:
            from sessions.models import SessionTableLog
            duration_agg = SessionTableLog.objects.filter(
                session__in=base_qs,
            ).aggregate(
                total_duration=models.Sum('duration_minutes'),
            )
            total_duration = duration_agg['total_duration'] or Decimal('0.00')
            avg_duration = (total_duration / total_sessions).quantize(Decimal('0.01'))

        # Avg revenue per session
        avg_revenue = None
        if total_sessions > 0:
            avg_revenue = (total_revenue / total_sessions).quantize(Decimal('0.01'))

        # Most used package
        most_used_package = None
        top_pkg = base_qs.filter(package__isnull=False).values(
            'package_id', 'package__name',
        ).annotate(
            count=models.Count('id'),
        ).order_by('-count').first()
        if top_pkg:
            most_used_package = {
                'id': top_pkg['package_id'],
                'name': top_pkg['package__name'],
                'count': top_pkg['count'],
            }

        return {
            'total_revenue': total_revenue,
            'total_sessions': total_sessions,
            'avg_duration_minutes': avg_duration,
            'avg_revenue_per_session': avg_revenue,
            'most_used_package': most_used_package,
        }

    # ------------------------------------------------------------------
    # Revenue Trend
    # ------------------------------------------------------------------
    @staticmethod
    def get_revenue_trend(
        outlet_ids: list[int],
        date_from: date | None = None,
        date_to: date | None = None,
        granularity: str = 'daily',
    ) -> tuple[str, list[dict]]:
        """
        Generate time-series data grouped by date (daily) or week (weekly).
        Returns (granularity, list of {date, revenue, session_count}).
        """
        base_qs = DashboardService._build_base_qs(outlet_ids, date_from, date_to)

        if granularity == 'weekly':
            grouped = base_qs.annotate(
                week=TruncWeek('started_at'),
            ).values('week').annotate(
                revenue=models.Sum('total_amount'),
                session_count=models.Count('id'),
            ).order_by('week')
            data = [
                {
                    'date': item['week'].date(),
                    'revenue': item['revenue'] or Decimal('0.00'),
                    'session_count': item['session_count'],
                }
                for item in grouped
            ]
        else:
            grouped = base_qs.annotate(
                day=TruncDate('started_at'),
            ).values('day').annotate(
                revenue=models.Sum('total_amount'),
                session_count=models.Count('id'),
            ).order_by('day')
            data = [
                {
                    'date': item['day'],
                    'revenue': item['revenue'] or Decimal('0.00'),
                    'session_count': item['session_count'],
                }
                for item in grouped
            ]

        return granularity, data

    # ------------------------------------------------------------------
    # Top Customers
    # ------------------------------------------------------------------
    @staticmethod
    def get_top_customers(
        outlet_ids: list[int],
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """
        Get top customers by total spend, grouped by customer_phone.
        Returns list of {customer_phone, customer_name, visit_count, total_spend}.
        """
        base_qs = DashboardService._build_base_qs(outlet_ids, date_from, date_to)

        grouped = base_qs.values(
            'customer_phone',
        ).annotate(
            visit_count=models.Count('id'),
            total_spend=models.Sum('total_amount'),
        ).order_by('-total_spend')[:limit]

        result = []
        for item in grouped:
            # Get the most recent customer_name for this phone
            latest_name = base_qs.filter(
                customer_phone=item['customer_phone'],
            ).order_by('-started_at').values_list('customer_name', flat=True).first()
            result.append({
                'customer_phone': item['customer_phone'],
                'customer_name': latest_name or '',
                'visit_count': item['visit_count'],
                'total_spend': item['total_spend'] or Decimal('0.00'),
            })

        return result