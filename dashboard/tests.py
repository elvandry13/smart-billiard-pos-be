from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User, Tenant, Outlet
from tables.models import TableType, Table, PricingRule
from packages.models import Package
from shifts.models import Shift
from sessions.models import PlaySession, SessionTableLog

from .services import DashboardService


# =============================================================================
# Service Unit Tests
# =============================================================================

class DashboardServiceTests(TestCase):
    """Test DashboardService business logic."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet1 = Outlet.objects.create(tenant=cls.tenant, name='Outlet 1', code='O1')
        cls.outlet2 = Outlet.objects.create(tenant=cls.tenant, name='Outlet 2', code='O2')
        cls.officer = User.objects.create_user(
            username='officer1', password='pass1234', role='officer',
            tenant=cls.tenant, outlet=cls.outlet1,
        )
        cls.table_type = TableType.objects.create(outlet=cls.outlet1, name='Standard')
        cls.table = Table.objects.create(
            outlet=cls.outlet1, name='Table 1', table_type=cls.table_type,
            status=Table.Status.AVAILABLE,
        )
        PricingRule.objects.create(
            outlet=cls.outlet1, table_type=cls.table_type, name='Standard Rate',
            day_type=PricingRule.DayType.WEEKDAY,
            start_time='00:00:00', end_time='23:59:59',
            price_per_minute=2.00, priority=1, is_active=True,
        )
        cls.pkg = Package.objects.create(
            outlet=cls.outlet1, name='Happy Hour', type=Package.PackageType.HAPPY_HOUR,
            duration_minutes=60, fixed_price=30000, is_active=True,
        )

    def _create_session(self, outlet, customer_name='Test', customer_phone='0812',
                         total_amount=Decimal('50000'), package=None,
                         started_at=None, status=PlaySession.Status.COMPLETED,
                         duration_minutes=30):
        """Helper: create a completed session with a table log."""
        now = timezone.now()
        if started_at is None:
            started_at = now - timedelta(minutes=duration_minutes)
        session = PlaySession.objects.create(
            outlet=outlet,
            shift=Shift.objects.create(
                outlet=outlet, officer=self.officer,
                opening_cash=50000, status=Shift.Status.CLOSED,
                closing_cash=100000, expected_cash=100000, difference=0,
            ),
            customer_name=customer_name,
            customer_phone=customer_phone,
            initial_table=self.table,
            officer_start=self.officer,
            package=package,
            status=status,
            subtotal=total_amount,
            total_amount=total_amount,
            ended_at=now,
        )
        # started_at has auto_now_add=True, so we must update it after creation
        PlaySession.objects.filter(pk=session.pk).update(started_at=started_at)
        session.refresh_from_db()
        SessionTableLog.objects.create(
            session=session,
            table=self.table,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=started_at,
            ended_at=now,
            amount=total_amount,
            duration_minutes=duration_minutes,
        )
        return session

    # ------------------------------------------------------------------
    # get_summary
    # ------------------------------------------------------------------
    def test_get_summary_returns_metrics(self):
        self._create_session(self.outlet1, total_amount=Decimal('50000'), duration_minutes=30)
        self._create_session(self.outlet1, total_amount=Decimal('30000'), duration_minutes=20,
                             customer_name='Test 2', customer_phone='0813')

        data = DashboardService.get_summary(outlet_ids=[self.outlet1.id])

        self.assertEqual(data['total_revenue'], Decimal('80000.00'))
        self.assertEqual(data['total_sessions'], 2)
        self.assertEqual(data['avg_duration_minutes'], Decimal('25.00'))  # (30+20)/2
        self.assertEqual(data['avg_revenue_per_session'], Decimal('40000.00'))

    def test_get_summary_empty_data_returns_zero(self):
        data = DashboardService.get_summary(outlet_ids=[self.outlet1.id])

        self.assertEqual(data['total_revenue'], Decimal('0.00'))
        self.assertEqual(data['total_sessions'], 0)
        self.assertIsNone(data['avg_duration_minutes'])
        self.assertIsNone(data['avg_revenue_per_session'])
        self.assertIsNone(data['most_used_package'])

    def test_get_summary_most_used_package(self):
        self._create_session(self.outlet1, total_amount=Decimal('30000'),
                             package=self.pkg, customer_name='A')
        self._create_session(self.outlet1, total_amount=Decimal('30000'),
                             package=self.pkg, customer_name='B')
        self._create_session(self.outlet1, total_amount=Decimal('50000'),
                             package=None, customer_name='C')

        data = DashboardService.get_summary(outlet_ids=[self.outlet1.id])

        self.assertIsNotNone(data['most_used_package'])
        self.assertEqual(data['most_used_package']['id'], self.pkg.id)
        self.assertEqual(data['most_used_package']['count'], 2)

    def test_get_summary_date_range_filters_correctly(self):
        today = date.today()
        self._create_session(self.outlet1, total_amount=Decimal('10000'),
                             started_at=timezone.now() - timedelta(days=10), duration_minutes=10)
        self._create_session(self.outlet1, total_amount=Decimal('20000'),
                             started_at=timezone.now() - timedelta(days=1), duration_minutes=20)
        self._create_session(self.outlet1, total_amount=Decimal('30000'),
                             started_at=timezone.now(), duration_minutes=30)

        data = DashboardService.get_summary(
            outlet_ids=[self.outlet1.id],
            date_from=today - timedelta(days=3),
            date_to=today,
        )

        self.assertEqual(data['total_sessions'], 2)  # only 1-day ago and today
        self.assertEqual(data['total_revenue'], Decimal('50000.00'))

    def test_get_summary_multiple_outlets(self):
        # Create a second table + pricing for outlet2
        table_type2 = TableType.objects.create(outlet=self.outlet2, name='Standard')
        table2 = Table.objects.create(
            outlet=self.outlet2, name='Table 2-1', table_type=table_type2,
            status=Table.Status.AVAILABLE,
        )
        PricingRule.objects.create(
            outlet=self.outlet2, table_type=table_type2, name='Standard Rate',
            day_type=PricingRule.DayType.WEEKDAY,
            start_time='00:00:00', end_time='23:59:59',
            price_per_minute=2.00, priority=1, is_active=True,
        )
        officer2 = User.objects.create_user(
            username='officer2', password='pass1234', role='officer',
            tenant=self.tenant, outlet=self.outlet2,
        )
        # Create sessions in both outlets
        s1 = PlaySession.objects.create(
            outlet=self.outlet1,
            shift=Shift.objects.create(
                outlet=self.outlet1, officer=self.officer,
                opening_cash=50000, status=Shift.Status.CLOSED,
                closing_cash=70000, expected_cash=70000, difference=0,
            ),
            customer_name='O1', customer_phone='0811',
            initial_table=self.table, officer_start=self.officer,
            status=PlaySession.Status.COMPLETED,
            subtotal=Decimal('40000'), total_amount=Decimal('40000'),
        )
        SessionTableLog.objects.create(
            session=s1, table=self.table,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=timezone.now() - timedelta(minutes=30),
            ended_at=timezone.now(), amount=Decimal('40000'), duration_minutes=30,
        )
        s2 = PlaySession.objects.create(
            outlet=self.outlet2,
            shift=Shift.objects.create(
                outlet=self.outlet2, officer=officer2,
                opening_cash=50000, status=Shift.Status.CLOSED,
                closing_cash=60000, expected_cash=60000, difference=0,
            ),
            customer_name='O2', customer_phone='0812',
            initial_table=table2, officer_start=officer2,
            status=PlaySession.Status.COMPLETED,
            subtotal=Decimal('60000'), total_amount=Decimal('60000'),
        )
        SessionTableLog.objects.create(
            session=s2, table=table2,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=timezone.now() - timedelta(minutes=40),
            ended_at=timezone.now(), amount=Decimal('60000'), duration_minutes=40,
        )

        data = DashboardService.get_summary(
            outlet_ids=[self.outlet1.id, self.outlet2.id],
        )
        self.assertEqual(data['total_revenue'], Decimal('100000.00'))
        self.assertEqual(data['total_sessions'], 2)
        self.assertEqual(data['avg_duration_minutes'], Decimal('35.00'))

    # ------------------------------------------------------------------
    # get_revenue_trend
    # ------------------------------------------------------------------
    def test_get_revenue_trend_daily(self):
        today = date.today()
        self._create_session(self.outlet1, total_amount=Decimal('10000'),
                             started_at=timezone.now() - timedelta(days=2), duration_minutes=10)
        self._create_session(self.outlet1, total_amount=Decimal('20000'),
                             started_at=timezone.now() - timedelta(days=1), duration_minutes=20)
        self._create_session(self.outlet1, total_amount=Decimal('30000'),
                             started_at=timezone.now(), duration_minutes=30)

        granularity, data = DashboardService.get_revenue_trend(
            outlet_ids=[self.outlet1.id],
            date_from=today - timedelta(days=5),
            date_to=today,
            granularity='daily',
        )

        self.assertEqual(granularity, 'daily')
        self.assertGreaterEqual(len(data), 3)

    def test_get_revenue_trend_weekly(self):
        self._create_session(self.outlet1, total_amount=Decimal('50000'),
                             started_at=timezone.now(), duration_minutes=30)
        self._create_session(self.outlet1, total_amount=Decimal('25000'),
                             started_at=timezone.now() - timedelta(weeks=1), duration_minutes=15)

        granularity, data = DashboardService.get_revenue_trend(
            outlet_ids=[self.outlet1.id],
            granularity='weekly',
        )

        self.assertEqual(granularity, 'weekly')
        self.assertGreaterEqual(len(data), 1)

    def test_get_revenue_trend_empty_returns_empty_list(self):
        granularity, data = DashboardService.get_revenue_trend(
            outlet_ids=[self.outlet1.id],
        )
        self.assertEqual(data, [])

    # ------------------------------------------------------------------
    # get_top_customers
    # ------------------------------------------------------------------
    def test_get_top_customers_returns_sorted(self):
        self._create_session(self.outlet1, customer_phone='081-A', total_amount=Decimal('10000'))
        self._create_session(self.outlet1, customer_phone='081-A', total_amount=Decimal('15000'),
                             customer_name='Cust A 2')
        self._create_session(self.outlet1, customer_phone='081-B', total_amount=Decimal('50000'))
        self._create_session(self.outlet1, customer_phone='081-C', total_amount=Decimal('30000'))

        data = DashboardService.get_top_customers(
            outlet_ids=[self.outlet1.id], limit=3,
        )

        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['customer_phone'], '081-B')   # 50000
        self.assertEqual(data[0]['total_spend'], Decimal('50000.00'))
        self.assertEqual(data[1]['customer_phone'], '081-C')   # 30000
        self.assertEqual(data[2]['customer_phone'], '081-A')   # 25000
        self.assertEqual(data[2]['total_spend'], Decimal('25000.00'))
        self.assertEqual(data[2]['visit_count'], 2)

    def test_get_top_customers_empty_returns_empty_list(self):
        data = DashboardService.get_top_customers(outlet_ids=[self.outlet1.id])
        self.assertEqual(data, [])

    def test_get_top_customers_respects_limit(self):
        for i in range(5):
            self._create_session(self.outlet1, customer_phone=f'081-{i}',
                                 total_amount=Decimal(str(10000 + i * 1000)),
                                 customer_name=f'Cust {i}')

        data = DashboardService.get_top_customers(
            outlet_ids=[self.outlet1.id], limit=2,
        )
        self.assertEqual(len(data), 2)

    def test_get_top_customers_excludes_non_completed(self):
        self._create_session(self.outlet1, customer_phone='081-RUN',
                             total_amount=Decimal('10000'), status=PlaySession.Status.RUNNING)
        self._create_session(self.outlet1, customer_phone='081-CANCEL',
                             total_amount=Decimal('20000'), status=PlaySession.Status.CANCELLED)
        self._create_session(self.outlet1, customer_phone='081-OK',
                             total_amount=Decimal('30000'))

        data = DashboardService.get_top_customers(outlet_ids=[self.outlet1.id])
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['customer_phone'], '081-OK')


# =============================================================================
# API Integration Tests
# =============================================================================

class DashboardAPITests(TestCase):
    """Test dashboard API endpoints."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet1 = Outlet.objects.create(tenant=cls.tenant, name='Outlet 1', code='O1')
        cls.outlet2 = Outlet.objects.create(tenant=cls.tenant, name='Outlet 2', code='O2')

        cls.owner = User.objects.create_user(
            username='owner1', password='pass1234', role='owner',
            tenant=cls.tenant, outlet=cls.outlet1,
        )
        cls.admin = User.objects.create_user(
            username='admin1', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet1,
        )
        cls.officer = User.objects.create_user(
            username='officer1', password='pass1234', role='officer',
            tenant=cls.tenant, outlet=cls.outlet1,
        )

        cls.table_type = TableType.objects.create(outlet=cls.outlet1, name='Standard')
        cls.table = Table.objects.create(
            outlet=cls.outlet1, name='Table 1', table_type=cls.table_type,
            status=Table.Status.AVAILABLE,
        )
        PricingRule.objects.create(
            outlet=cls.outlet1, table_type=cls.table_type, name='Standard Rate',
            day_type=PricingRule.DayType.WEEKDAY,
            start_time='00:00:00', end_time='23:59:59',
            price_per_minute=2.00, priority=1, is_active=True,
        )

    def setUp(self):
        self.client = APIClient()
        shift = Shift.objects.create(
            outlet=self.outlet1, officer=self.officer,
            opening_cash=50000, status=Shift.Status.CLOSED,
            closing_cash=70000, expected_cash=70000, difference=0,
        )
        now = timezone.now()
        session = PlaySession.objects.create(
            outlet=self.outlet1, shift=shift, customer_name='Test',
            customer_phone='0812', initial_table=self.table,
            officer_start=self.officer, status=PlaySession.Status.COMPLETED,
            subtotal=Decimal('50000'), total_amount=Decimal('50000'),
            ended_at=now,
        )
        # started_at has auto_now_add=True, so we must update it after creation
        PlaySession.objects.filter(pk=session.pk).update(started_at=now - timedelta(minutes=30))
        session.refresh_from_db()
        SessionTableLog.objects.create(
            session=session, table=self.table,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=now - timedelta(minutes=30),
            ended_at=now, amount=Decimal('50000'), duration_minutes=30,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    def test_owner_can_get_summary(self):
        self._auth(self.owner)
        url = reverse('dashboard-summary')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('total_revenue', resp.data)
        self.assertIn('total_sessions', resp.data)

    def test_owner_sees_all_outlets(self):
        # Create a session in outlet2
        table_type2 = TableType.objects.create(outlet=self.outlet2, name='Standard')
        table2 = Table.objects.create(
            outlet=self.outlet2, name='Table 2-1', table_type=table_type2,
            status=Table.Status.AVAILABLE,
        )
        PricingRule.objects.create(
            outlet=self.outlet2, table_type=table_type2, name='Standard Rate',
            day_type=PricingRule.DayType.WEEKDAY,
            start_time='00:00:00', end_time='23:59:59',
            price_per_minute=2.00, priority=1, is_active=True,
        )
        officer2 = User.objects.create_user(
            username='officer2', password='pass1234', role='officer',
            tenant=self.tenant, outlet=self.outlet2,
        )
        shift2 = Shift.objects.create(
            outlet=self.outlet2, officer=officer2,
            opening_cash=50000, status=Shift.Status.CLOSED,
            closing_cash=60000, expected_cash=60000, difference=0,
        )
        s2 = PlaySession.objects.create(
            outlet=self.outlet2, shift=shift2, customer_name='O2',
            customer_phone='0813', initial_table=table2,
            officer_start=officer2, status=PlaySession.Status.COMPLETED,
            subtotal=Decimal('60000'), total_amount=Decimal('60000'),
        )
        SessionTableLog.objects.create(
            session=s2, table=table2,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=timezone.now() - timedelta(minutes=40),
            ended_at=timezone.now(), amount=Decimal('60000'), duration_minutes=40,
        )

        self._auth(self.owner)
        url = reverse('dashboard-summary')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['total_sessions'], 2)
        self.assertEqual(resp.data['total_revenue'], '110000.00')

    def test_admin_sees_only_own_outlet(self):
        # Owner already created in setUp - let's verify admin only sees outlet1
        self._auth(self.admin)
        url = reverse('dashboard-summary')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['total_sessions'], 1)

    def test_officer_cannot_access_dashboard(self):
        self._auth(self.officer)
        url = reverse('dashboard-summary')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_summary_unauthenticated_fails(self):
        url = reverse('dashboard-summary')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # ---------------------------------------------------------------
    # Revenue Trend
    # ---------------------------------------------------------------
    def test_owner_can_get_revenue_trend(self):
        self._auth(self.owner)
        url = reverse('dashboard-revenue-trend')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('granularity', resp.data)
        self.assertIn('data', resp.data)

    def test_revenue_trend_with_granularity_param(self):
        self._auth(self.owner)
        url = reverse('dashboard-revenue-trend') + '?granularity=weekly'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['granularity'], 'weekly')

    def test_revenue_trend_invalid_granularity(self):
        self._auth(self.owner)
        url = reverse('dashboard-revenue-trend') + '?granularity=yearly'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------------------------------------------------------
    # Top Customers
    # ---------------------------------------------------------------
    def test_owner_can_get_top_customers(self):
        self._auth(self.owner)
        url = reverse('dashboard-top-customers')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('data', resp.data)

    def test_top_customers_with_limit_param(self):
        self._auth(self.owner)
        url = reverse('dashboard-top-customers') + '?limit=5'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_top_customers_with_dates(self):
        self._auth(self.owner)
        today = date.today()
        url = (
            reverse('dashboard-top-customers')
            + f'?date_from={today - timedelta(days=7)}&date_to={today}'
        )
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)