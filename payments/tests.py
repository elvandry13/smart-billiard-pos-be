from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User, Tenant, Outlet
from tables.models import TableType, Table, PricingRule
from shifts.models import Shift
from sessions.models import PlaySession
from sessions.services import SessionService
from payments.models import Payment


class PaymentAPITests(TestCase):
    """Test suite untuk Payment API."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet = Outlet.objects.create(
            tenant=cls.tenant, name='Test Outlet', code='TO',
        )
        cls.other_outlet = Outlet.objects.create(
            tenant=cls.tenant, name='Other Outlet', code='OO',
        )
        cls.officer = User.objects.create_user(
            username='officer1', password='pass1234', role='officer',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.admin = User.objects.create_user(
            username='admin1', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.other_officer = User.objects.create_user(
            username='officer2', password='pass1234', role='officer',
            tenant=cls.tenant, outlet=cls.other_outlet,
        )
        cls.super_admin = User.objects.create_superuser(username='super', password='pass1234')

        cls.table_type = TableType.objects.create(outlet=cls.outlet, name='Standard')
        cls.table = Table.objects.create(
            outlet=cls.outlet, name='Table 1', table_type=cls.table_type,
            status=Table.Status.AVAILABLE,
        )

        cls.pricing_rule = PricingRule.objects.create(
            outlet=cls.outlet, table_type=cls.table_type, name='Standard Rate',
            day_type=PricingRule.DayType.WEEKDAY,
            start_time='00:00:00', end_time='23:59:59',
            price_per_minute=Decimal('2.00'), priority=1, is_active=True,
        )

    def setUp(self):
        self.shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self.client = APIClient()

    def _create_completed_session(self, **kwargs):
        """Helper: buka dan selesaikan sesi, return session."""
        session = SessionService.open_session(
            outlet_id=self.outlet.id,
            shift_id=self.shift.id,
            customer_name=kwargs.get('customer_name', 'John Doe'),
            customer_phone=kwargs.get('customer_phone', '081234567890'),
            initial_table_id=self.table.id,
            officer_start_id=self.officer.id,
        )
        SessionService.end_session(
            session_id=session.id,
            officer_end_id=kwargs.get('officer_end_id', self.officer.id),
        )
        session.refresh_from_db()
        return session

    def _create_payment_payload(self, session, method='cash'):
        return {
            'session_id': session.id,
            'method': method,
            'amount': str(session.total_amount),
        }

    # --- Create Payment ---

    def test_create_payment_for_completed_session(self):
        """Sukses create payment cash untuk session completed."""
        session = self._create_completed_session()
        self.client.force_authenticate(user=self.officer)
        payload = self._create_payment_payload(session)

        url = reverse('payment-list')
        resp = self.client.post(url, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['session_id'], session.id)
        self.assertEqual(resp.data['method'], 'cash')
        self.assertEqual(resp.data['status'], 'paid')

    def test_create_payment_amount_must_match_total(self):
        """Gagal jika amount ≠ session.total_amount."""
        session = self._create_completed_session()
        self.client.force_authenticate(user=self.officer)
        payload = {
            'session_id': session.id,
            'method': 'cash',
            'amount': str(session.total_amount + Decimal('10000')),
        }

        url = reverse('payment-list')
        resp = self.client.post(url, payload, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('amount', resp.data)

    def test_create_payment_only_one_paid_per_session(self):
        """Gagal jika session sudah punya Payment paid."""
        session = self._create_completed_session()
        self.client.force_authenticate(user=self.officer)
        payload = self._create_payment_payload(session)

        url = reverse('payment-list')
        resp1 = self.client.post(url, payload, format='json')
        self.assertEqual(resp1.status_code, status.HTTP_201_CREATED)

        resp2 = self.client.post(url, payload, format='json')
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('session', resp2.data)

    def test_create_payment_session_not_completed(self):
        """Gagal jika session masih running."""
        session = SessionService.open_session(
            outlet_id=self.outlet.id,
            shift_id=self.shift.id,
            customer_name='Jane',
            customer_phone='081111',
            initial_table_id=self.table.id,
            officer_start_id=self.officer.id,
        )
        self.client.force_authenticate(user=self.officer)
        payload = {
            'session_id': session.id,
            'method': 'cash',
            'amount': '10000',
        }

        url = reverse('payment-list')
        resp = self.client.post(url, payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('session', resp.data)

    def test_list_only_own_outlet(self):
        """Officer hanya lihat payment outlet-nya."""
        session1 = self._create_completed_session(customer_name='A')
        self.client.force_authenticate(user=self.officer)
        self.client.post(
            reverse('payment-list'),
            self._create_payment_payload(session1),
            format='json',
        )

        # Login sebagai other_officer — seharusnya tidak lihat payment outlet lain
        self.client.force_authenticate(user=self.other_officer)
        resp = self.client.get(reverse('payment-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 0)

    def test_super_admin_can_see_all(self):
        """SuperAdmin bisa lihat semua payment."""
        session = self._create_completed_session()
        self.client.force_authenticate(user=self.officer)
        self.client.post(
            reverse('payment-list'),
            self._create_payment_payload(session),
            format='json',
        )

        self.client.force_authenticate(user=self.super_admin)
        resp = self.client.get(reverse('payment-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_officer_can_create_payment(self):
        """Officer bisa create payment."""
        session = self._create_completed_session()
        self.client.force_authenticate(user=self.officer)
        resp = self.client.post(
            reverse('payment-list'),
            self._create_payment_payload(session),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_admin_can_create_payment(self):
        """Admin bisa create payment."""
        session = self._create_completed_session()
        self.client.force_authenticate(user=self.admin)
        resp = self.client.post(
            reverse('payment-list'),
            self._create_payment_payload(session),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_unauthenticated_cannot_create(self):
        """Unauthenticated user tidak bisa create payment."""
        session = self._create_completed_session()
        resp = self.client.post(
            reverse('payment-list'),
            self._create_payment_payload(session),
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)