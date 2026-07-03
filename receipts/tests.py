"""Test suite untuk Receipt API."""
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
from payments.services import PaymentService
from receipts.models import Receipt, InvoiceSequence


class ReceiptAPITests(TestCase):
    """Test suite untuk Receipt API."""

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

    def _create_paid_session(self, **kwargs):
        """Helper: open → end → pay session, return session."""
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
        PaymentService.create_payment(
            session_id=session.id,
            outlet_id=self.outlet.id,
            method=Payment.Method.CASH,
            amount=session.total_amount,
            created_by_id=self.officer.id,
        )
        return session

    def _create_completed_session(self, **kwargs):
        """Helper: open → end session."""
        session = SessionService.open_session(
            outlet_id=self.outlet.id,
            shift_id=self.shift.id,
            customer_name=kwargs.get('customer_name', 'Jane Doe'),
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

    # --- Generate Receipt ---

    def test_generate_receipt_success(self):
        """Sukses generate receipt untuk session paid."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.officer)

        url = reverse('receipt-list')
        resp = self.client.post(url, {'session_id': session.id}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['session_id'], session.id)
        self.assertIn('invoice_number', resp.data)
        self.assertIn('pdf_file', resp.data)
        self.assertTrue(resp.data['invoice_number'].startswith('TO-'))
        # Verify Receipt exists in DB
        self.assertEqual(Receipt.objects.count(), 1)
        receipt = Receipt.objects.first()
        self.assertIsNotNone(receipt.pdf_file)

    def test_generate_receipt_fails_not_completed(self):
        """Gagal generate receipt untuk session running."""
        session = SessionService.open_session(
            outlet_id=self.outlet.id,
            shift_id=self.shift.id,
            customer_name='Running',
            customer_phone='081111',
            initial_table_id=self.table.id,
            officer_start_id=self.officer.id,
        )
        self.client.force_authenticate(user=self.officer)

        url = reverse('receipt-list')
        resp = self.client.post(url, {'session_id': session.id}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('session', resp.data)

    def test_generate_receipt_fails_not_paid(self):
        """Gagal generate receipt untuk session completed tapi belum paid."""
        session = self._create_completed_session()
        self.client.force_authenticate(user=self.officer)

        url = reverse('receipt-list')
        resp = self.client.post(url, {'session_id': session.id}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('session', resp.data)

    def test_receipt_list_only_own_outlet(self):
        """Officer hanya lihat receipt outlet-nya."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.officer)
        self.client.post(reverse('receipt-list'), {'session_id': session.id}, format='json')

        # Login sebagai other_officer
        self.client.force_authenticate(user=self.other_officer)
        resp = self.client.get(reverse('receipt-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 0)

    def test_cross_outlet_receipt_creation_rejected(self):
        """Officer tidak bisa generate receipt untuk session outlet lain."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.other_officer)

        url = reverse('receipt-list')
        resp = self.client.post(url, {'session_id': session.id}, format='json')

        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('session', resp.data)
        self.assertEqual(Receipt.objects.count(), 0)

    def test_super_admin_can_see_all(self):
        """SuperAdmin bisa lihat semua receipt."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.officer)
        self.client.post(reverse('receipt-list'), {'session_id': session.id}, format='json')

        self.client.force_authenticate(user=self.super_admin)
        resp = self.client.get(reverse('receipt-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)

    def test_officer_can_generate(self):
        """Officer bisa generate receipt."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.officer)

        resp = self.client.post(
            reverse('receipt-list'),
            {'session_id': session.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_admin_can_generate(self):
        """Admin bisa generate receipt."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.admin)

        resp = self.client.post(
            reverse('receipt-list'),
            {'session_id': session.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_unauthenticated_cannot_generate(self):
        """Unauthenticated user tidak bisa generate receipt."""
        session = self._create_paid_session()

        resp = self.client.post(
            reverse('receipt-list'),
            {'session_id': session.id},
            format='json',
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_download_receipt_success(self):
        """Sukses download PDF receipt."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.officer)
        gen_resp = self.client.post(
            reverse('receipt-list'),
            {'session_id': session.id},
            format='json',
        )
        receipt_id = gen_resp.data['id']

        resp = self.client.get(
            reverse('receipt-download', args=[receipt_id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def test_invoice_number_increments(self):
        """Invoice number bertambah sequential."""
        session1 = self._create_paid_session(customer_name='A')
        session2 = self._create_paid_session(customer_name='B')

        self.client.force_authenticate(user=self.officer)

        resp1 = self.client.post(
            reverse('receipt-list'),
            {'session_id': session1.id},
            format='json',
        )
        resp2 = self.client.post(
            reverse('receipt-list'),
            {'session_id': session2.id},
            format='json',
        )

        inv1 = resp1.data['invoice_number']
        inv2 = resp2.data['invoice_number']

        # Format: TO-YYYYMMDD-0001, TO-YYYYMMDD-0002
        # Verify sequence is incremented
        self.assertNotEqual(inv1, inv2)
        seq1 = int(inv1.split('-')[-1])
        seq2 = int(inv2.split('-')[-1])
        self.assertEqual(seq2, seq1 + 1)

    def test_receipt_detail(self):
        """Lihat detail receipt."""
        session = self._create_paid_session()
        self.client.force_authenticate(user=self.officer)
        gen_resp = self.client.post(
            reverse('receipt-list'),
            {'session_id': session.id},
            format='json',
        )
        receipt_id = gen_resp.data['id']

        resp = self.client.get(
            reverse('receipt-detail', args=[receipt_id]),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], receipt_id)
        self.assertEqual(resp.data['session_id'], session.id)
        self.assertIn('invoice_number', resp.data)
        self.assertIn('pdf_file', resp.data)
        self.assertIn('outlet_name', resp.data)