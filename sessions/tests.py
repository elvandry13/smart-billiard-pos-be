from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User, Tenant, Outlet
from tables.models import TableType, Table, PricingRule, AdditionalFee
from packages.models import Package
from shifts.models import Shift

from .models import PlaySession, SessionTableLog


class SessionServiceTests(TestCase):
    """Test SessionService business logic (unit tests)."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet = Outlet.objects.create(tenant=cls.tenant, name='Test Outlet', code='TO')
        cls.officer = User.objects.create_user(
            username='officer1', password='pass1234', role='officer',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.super_admin = User.objects.create_superuser(username='super', password='pass1234')

        cls.table_type = TableType.objects.create(outlet=cls.outlet, name='Standard')
        cls.table = Table.objects.create(
            outlet=cls.outlet, name='Table 1', table_type=cls.table_type,
            status=Table.Status.AVAILABLE,
        )
        cls.table2 = Table.objects.create(
            outlet=cls.outlet, name='Table 2', table_type=cls.table_type,
            status=Table.Status.AVAILABLE,
        )

        cls.pricing_rule = PricingRule.objects.create(
            outlet=cls.outlet, table_type=cls.table_type, name='Standard Rate',
            day_type=PricingRule.DayType.WEEKDAY,
            start_time='00:00:00', end_time='23:59:59',
            price_per_minute=2.00, priority=1, is_active=True,
        )

    def setUp(self):
        self.shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )

    # --- Open Session ---

    def test_open_session_basic(self):
        from .services import SessionService
        session = SessionService.open_session(
            outlet_id=self.outlet.id,
            shift_id=self.shift.id,
            customer_name='John Doe',
            customer_phone='081234567890',
            initial_table_id=self.table.id,
            officer_start_id=self.officer.id,
        )
        self.assertEqual(session.status, PlaySession.Status.RUNNING)
        self.assertEqual(session.outlet, self.outlet)
        self.assertEqual(session.customer_name, 'John Doe')

        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.OCCUPIED)

        log = session.table_logs.first()
        self.assertIsNotNone(log)
        self.assertEqual(log.table, self.table)
        self.assertEqual(log.rate_source_type, SessionTableLog.RateSourceType.PRICING_RULE)
        self.assertIsNone(log.ended_at)

    def test_open_session_with_package(self):
        pkg = Package.objects.create(
            outlet=self.outlet, name='Happy Hour', type=Package.PackageType.HAPPY_HOUR,
            duration_minutes=60, fixed_price=30000, is_active=True,
        )
        from .services import SessionService
        session = SessionService.open_session(
            outlet_id=self.outlet.id,
            shift_id=self.shift.id,
            customer_name='Jane Doe',
            customer_phone='087654321',
            initial_table_id=self.table.id,
            officer_start_id=self.officer.id,
            package_id=pkg.id,
        )
        self.assertEqual(session.package, pkg)
        log = session.table_logs.first()
        self.assertEqual(log.rate_source_type, SessionTableLog.RateSourceType.PACKAGE_RATE)
        self.assertIn('fixed_price', log.rate_source_snapshot)

    def test_open_session_fails_if_shift_not_open(self):
        self.shift.status = Shift.Status.CLOSED
        self.shift.closing_cash = 60000
        self.shift.expected_cash = 50000
        self.shift.difference = 10000
        self.shift.save()
        from .services import SessionService
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            SessionService.open_session(
                outlet_id=self.outlet.id, shift_id=self.shift.id,
                customer_name='Fail', customer_phone='',
                initial_table_id=self.table.id, officer_start_id=self.officer.id,
            )

    def test_open_session_fails_if_table_not_available(self):
        self.table.status = Table.Status.MAINTENANCE
        self.table.save()
        from .services import SessionService
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            SessionService.open_session(
                outlet_id=self.outlet.id, shift_id=self.shift.id,
                customer_name='Fail', customer_phone='',
                initial_table_id=self.table.id, officer_start_id=self.officer.id,
            )

    def test_open_session_fails_if_package_not_active(self):
        pkg = Package.objects.create(
            outlet=self.outlet, name='Inactive Pkg', type=Package.PackageType.PER_MINUTE,
            price_per_minute=3.00, is_active=False,
        )
        from .services import SessionService
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            SessionService.open_session(
                outlet_id=self.outlet.id, shift_id=self.shift.id,
                customer_name='Fail', customer_phone='',
                initial_table_id=self.table.id, officer_start_id=self.officer.id,
                package_id=pkg.id,
            )

    # --- Transfer Table ---

    def test_transfer_table_basic(self):
        from .services import SessionService
        session = SessionService.open_session(
            outlet_id=self.outlet.id, shift_id=self.shift.id,
            customer_name='Transfer Test', customer_phone='',
            initial_table_id=self.table.id, officer_start_id=self.officer.id,
        )
        new_log = SessionService.transfer_table(
            session_id=session.id,
            new_table_id=self.table2.id,
            officer_id=self.officer.id,
        )
        self.table.refresh_from_db()
        self.table2.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.AVAILABLE)
        self.assertEqual(self.table2.status, Table.Status.OCCUPIED)

        logs = session.table_logs.all()
        self.assertEqual(logs.count(), 2)
        old_log = logs.first()
        new_log = logs.last()
        self.assertIsNotNone(old_log.ended_at)
        self.assertIsNotNone(old_log.amount)
        self.assertIsNone(new_log.ended_at)
        self.assertEqual(new_log.table, self.table2)

    def test_transfer_fails_if_session_not_running(self):
        from .services import SessionService
        from django.core.exceptions import ValidationError
        session = PlaySession.objects.create(
            outlet=self.outlet, shift=self.shift, customer_name='Done',
            customer_phone='', initial_table=self.table,
            officer_start=self.officer, status=PlaySession.Status.COMPLETED,
            subtotal=Decimal('0'), additional_fee_total=Decimal('0'),
            total_amount=Decimal('0'),
        )
        with self.assertRaises(ValidationError):
            SessionService.transfer_table(
                session_id=session.id, new_table_id=self.table2.id, officer_id=self.officer.id,
            )

    # --- End Session ---

    def test_end_session_basic(self):
        from .services import SessionService
        session = SessionService.open_session(
            outlet_id=self.outlet.id, shift_id=self.shift.id,
            customer_name='End Test', customer_phone='',
            initial_table_id=self.table.id, officer_start_id=self.officer.id,
        )
        # Simulate time passing
        active_log = session.table_logs.first()
        active_log.started_at = timezone.now() - timedelta(minutes=30)
        active_log.save()
        session = SessionService.end_session(
            session_id=session.id, officer_end_id=self.officer.id,
        )
        self.assertEqual(session.status, PlaySession.Status.COMPLETED)
        self.assertIsNotNone(session.subtotal)
        self.assertIsNotNone(session.total_amount)
        self.assertIsNotNone(session.ended_at)
        self.assertEqual(session.officer_end, self.officer)

        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.AVAILABLE)

    # --- Cancel Session ---

    def test_cancel_session_basic(self):
        from .services import SessionService
        session = SessionService.open_session(
            outlet_id=self.outlet.id, shift_id=self.shift.id,
            customer_name='Cancel Test', customer_phone='',
            initial_table_id=self.table.id, officer_start_id=self.officer.id,
        )
        session = SessionService.cancel_session(
            session_id=session.id, officer_end_id=self.officer.id,
            cancel_reason='Dibatalkan oleh customer',
        )
        self.assertEqual(session.status, PlaySession.Status.CANCELLED)
        self.assertEqual(session.cancel_reason, 'Dibatalkan oleh customer')
        self.assertIsNone(session.subtotal)
        self.assertIsNone(session.total_amount)

        self.table.refresh_from_db()
        self.assertEqual(self.table.status, Table.Status.AVAILABLE)


class SessionAPITests(TestCase):
    """Test PlaySession API endpoints (integration tests)."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet = Outlet.objects.create(tenant=cls.tenant, name='Test Outlet', code='TO')

        cls.officer = User.objects.create_user(
            username='officer1', password='pass1234', role='officer',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.admin = User.objects.create_user(
            username='admin1', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.super_admin = User.objects.create_superuser(username='super', password='pass1234')

        cls.table_type = TableType.objects.create(outlet=cls.outlet, name='Standard')
        cls.table = Table.objects.create(
            outlet=cls.outlet, name='Table 1', table_type=cls.table_type,
            status=Table.Status.AVAILABLE,
        )
        cls.table2 = Table.objects.create(
            outlet=cls.outlet, name='Table 2', table_type=cls.table_type,
            status=Table.Status.AVAILABLE,
        )

        cls.pricing_rule = PricingRule.objects.create(
            outlet=cls.outlet, table_type=cls.table_type, name='Standard Rate',
            day_type=PricingRule.DayType.WEEKDAY,
            start_time='00:00:00', end_time='23:59:59',
            price_per_minute=2.00, priority=1, is_active=True,
        )

    def setUp(self):
        self.client = APIClient()
        self.shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    # ---------------------------------------------------------------
    # Open Session (POST /api/sessions/open/)
    # ---------------------------------------------------------------

    def test_officer_can_open_session(self):
        self._auth(self.officer)
        url = reverse('playsession-open')
        resp = self.client.post(url, {
            'shift_id': self.shift.id,
            'customer_name': 'John',
            'customer_phone': '08123',
            'initial_table_id': self.table.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['status'], 'running')
        self.assertEqual(resp.data['customer_name'], 'John')

    def test_open_session_without_auth_fails(self):
        url = reverse('playsession-open')
        resp = self.client.post(url, {
            'shift_id': self.shift.id,
            'customer_name': 'John',
            'initial_table_id': self.table.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_cannot_open_session(self):
        self._auth(self.admin)
        url = reverse('playsession-open')
        resp = self.client.post(url, {
            'shift_id': self.shift.id,
            'customer_name': 'John',
            'initial_table_id': self.table.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_open_session_missing_shift_fails(self):
        self._auth(self.officer)
        url = reverse('playsession-open')
        resp = self.client.post(url, {
            'customer_name': 'John',
            'initial_table_id': self.table.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------------------------------------------------------
    # Transfer Table (POST /api/sessions/transfer-table/)
    # ---------------------------------------------------------------

    def test_officer_can_transfer_table(self):
        self._auth(self.officer)
        # Open first
        open_url = reverse('playsession-open')
        resp = self.client.post(open_url, {
            'shift_id': self.shift.id,
            'customer_name': 'Transfer',
            'initial_table_id': self.table.id,
        }, format='json')
        session_id = resp.data['id']

        # Transfer
        transfer_url = reverse('playsession-transfer-table')
        resp = self.client.post(transfer_url, {
            'session_id': session_id,
            'new_table_id': self.table2.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['table'], self.table2.id)

    # ---------------------------------------------------------------
    # End Session (POST /api/sessions/end-session/)
    # ---------------------------------------------------------------

    def test_officer_can_end_session(self):
        self._auth(self.officer)
        # Open
        open_url = reverse('playsession-open')
        resp = self.client.post(open_url, {
            'shift_id': self.shift.id,
            'customer_name': 'End Me',
            'initial_table_id': self.table.id,
        }, format='json')
        session_id = resp.data['id']

        # End
        end_url = reverse('playsession-end-session')
        resp = self.client.post(end_url, {
            'session_id': session_id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'completed')
        self.assertIsNotNone(resp.data['total_amount'])

    # ---------------------------------------------------------------
    # Cancel Session (POST /api/sessions/cancel-session/)
    # ---------------------------------------------------------------

    def test_officer_can_cancel_session(self):
        self._auth(self.officer)
        # Open
        open_url = reverse('playsession-open')
        resp = self.client.post(open_url, {
            'shift_id': self.shift.id,
            'customer_name': 'Cancel Me',
            'initial_table_id': self.table.id,
        }, format='json')
        session_id = resp.data['id']

        # Cancel
        cancel_url = reverse('playsession-cancel-session')
        resp = self.client.post(cancel_url, {
            'session_id': session_id,
            'cancel_reason': 'Test cancel',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'cancelled')
        self.assertEqual(resp.data['cancel_reason'], 'Test cancel')

    # ---------------------------------------------------------------
    # List / Retrieve Sessions
    # ---------------------------------------------------------------

    def test_officer_can_list_sessions(self):
        session = PlaySession.objects.create(
            outlet=self.outlet, shift=self.shift, customer_name='List',
            customer_phone='', initial_table=self.table,
            officer_start=self.officer, status=PlaySession.Status.RUNNING,
        )
        SessionTableLog.objects.create(
            session=session, table=self.table,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=timezone.now(),
        )
        self._auth(self.officer)
        url = reverse('playsession-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_officer_can_retrieve_session(self):
        session = PlaySession.objects.create(
            outlet=self.outlet, shift=self.shift, customer_name='Detail',
            customer_phone='', initial_table=self.table,
            officer_start=self.officer, status=PlaySession.Status.RUNNING,
        )
        SessionTableLog.objects.create(
            session=session, table=self.table,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=timezone.now(),
        )
        self._auth(self.officer)
        url = reverse('playsession-detail', args=[session.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['customer_name'], 'Detail')
        self.assertIn('table_logs', resp.data)

    # ---------------------------------------------------------------
    # Table Logs (custom actions)
    # ---------------------------------------------------------------

    def test_officer_can_list_table_logs(self):
        session = PlaySession.objects.create(
            outlet=self.outlet, shift=self.shift, customer_name='Logs',
            customer_phone='', initial_table=self.table,
            officer_start=self.officer, status=PlaySession.Status.RUNNING,
        )
        SessionTableLog.objects.create(
            session=session, table=self.table,
            rate_source_type=SessionTableLog.RateSourceType.PRICING_RULE,
            rate_source_snapshot={'price_per_minute': '2.00'},
            started_at=timezone.now(),
        )
        self._auth(self.officer)
        url = reverse('playsession-table-logs', args=[session.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data), 1)

    # ---------------------------------------------------------------
    # Scoping: officer hanya lihat sessions di outlet-nya
    # ---------------------------------------------------------------

    def test_officer_cannot_see_other_outlet_sessions(self):
        other_tenant = Tenant.objects.create(name='Other', code='OT')
        other_outlet = Outlet.objects.create(tenant=other_tenant, name='Other', code='OO')
        other_officer = User.objects.create_user(
            username='other_officer', password='pass1234', role='officer',
            tenant=other_tenant, outlet=other_outlet,
        )
        other_shift = Shift.objects.create(
            outlet=other_outlet, officer=other_officer,
            opening_cash=30000, status=Shift.Status.OPEN,
        )
        other_table_type = TableType.objects.create(outlet=other_outlet, name='Standard')
        other_table = Table.objects.create(
            outlet=other_outlet, name='Other T1', table_type=other_table_type,
            status=Table.Status.AVAILABLE,
        )
        pricing_rule = PricingRule.objects.create(
            outlet=other_outlet, table_type=other_table_type, name='Rule',
            day_type='weekday', start_time='00:00:00', end_time='23:59:59',
            price_per_minute=2.00, priority=1, is_active=True,
        )
        PlaySession.objects.create(
            outlet=other_outlet, shift=other_shift, customer_name='Other Session',
            customer_phone='', initial_table=other_table,
            officer_start=other_officer, status=PlaySession.Status.RUNNING,
        )

        self._auth(self.officer)
        url = reverse('playsession-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 0)  # tidak ada session untuk officer ini