from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, Tenant, Outlet
from shifts.models import Shift


class ShiftAPITests(TestCase):
    """Test Shift API — open/close shift, permissions, validation."""

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
        cls.super_admin = User.objects.create_superuser(
            username='super', password='pass1234',
        )
        # Officer di outlet lain untuk test scoping
        cls.other_tenant = Tenant.objects.create(name='Other Tenant', code='OT')
        cls.other_outlet = Outlet.objects.create(
            tenant=cls.other_tenant, name='Other Outlet', code='OO',
        )
        cls.other_officer = User.objects.create_user(
            username='other_officer', password='pass1234', role='officer',
            tenant=cls.other_tenant, outlet=cls.other_outlet,
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    # --- Officer: Open Shift ---

    def test_officer_can_open_shift(self):
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '50000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Shift.objects.count(), 1)
        shift = Shift.objects.first()
        self.assertEqual(shift.officer, self.officer)
        self.assertEqual(shift.outlet, self.outlet)
        self.assertEqual(shift.status, Shift.Status.OPEN)
        self.assertEqual(float(shift.opening_cash), 50000.00)

    def test_officer_can_open_shift_with_notes(self):
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '100000.00',
            'notes': 'Morning shift',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        shift = Shift.objects.first()
        self.assertEqual(shift.notes, 'Morning shift')

    # --- Officer: Close Shift ---

    def test_officer_can_close_shift(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.officer)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.patch(url, {
            'status': 'closed',
            'closing_cash': '65000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        shift.refresh_from_db()
        self.assertEqual(shift.status, Shift.Status.CLOSED)
        self.assertEqual(float(shift.closing_cash), 65000.00)
        self.assertEqual(float(shift.expected_cash), 50000.00)
        self.assertEqual(float(shift.difference), 15000.00)
        self.assertIsNotNone(shift.closed_at)

    def test_close_shift_without_closing_cash_fails(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.officer)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.patch(url, {
            'status': 'closed',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('closing_cash', resp.data)

    # --- Validation: Opening Cash ---

    def test_open_shift_with_zero_opening_cash_fails(self):
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '0.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('opening_cash', resp.data)

    def test_open_shift_with_negative_opening_cash_fails(self):
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '-100.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('opening_cash', resp.data)

    def test_open_shift_without_opening_cash_fails(self):
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('opening_cash', resp.data)

    # --- One Officer, One Open Shift ---

    def test_officer_cannot_open_second_shift(self):
        Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '30000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('officer', resp.data)
        self.assertEqual(Shift.objects.count(), 1)

    def test_officer_can_open_new_shift_after_closing(self):
        Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        # Close first shift
        shift = Shift.objects.first()
        shift.status = Shift.Status.CLOSED
        shift.closing_cash = 60000
        shift.expected_cash = shift.opening_cash
        shift.difference = shift.closing_cash - shift.expected_cash
        shift.save()
        # Open new shift
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '40000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Shift.objects.filter(status=Shift.Status.OPEN).count(), 1)

    # --- Cannot Modify Closed Shift ---

    def test_cannot_reopen_closed_shift(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        shift.status = Shift.Status.CLOSED
        shift.closing_cash = 60000
        shift.expected_cash = shift.opening_cash
        shift.difference = shift.closing_cash - shift.expected_cash
        shift.save()

        self._auth(self.officer)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.patch(url, {'status': 'open'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Admin Read-Only ---

    def test_admin_can_list_shifts(self):
        Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.admin)
        url = reverse('shifts:shift-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_admin_can_retrieve_shift(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.admin)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['status'], 'open')

    def test_admin_cannot_create_shift(self):
        self._auth(self.admin)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '50000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_close_shift(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.admin)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.patch(url, {
            'status': 'closed',
            'closing_cash': '60000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cannot_delete_shift(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.admin)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # --- Officer Scoping ---

    def test_officer_cannot_see_other_officer_shift(self):
        Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        Shift.objects.create(
            outlet=self.other_outlet, officer=self.other_officer,
            opening_cash=30000, status=Shift.Status.OPEN,
        )
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['officer'], self.officer.id)

    # --- Super Admin ---

    def test_super_admin_can_see_all_shifts(self):
        Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        Shift.objects.create(
            outlet=self.other_outlet, officer=self.other_officer,
            opening_cash=30000, status=Shift.Status.OPEN,
        )
        self._auth(self.super_admin)
        url = reverse('shifts:shift-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 2)

    def test_super_admin_can_create_shift(self):
        self._auth(self.super_admin)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'officer': self.officer.id,
            'opening_cash': '75000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        shift = Shift.objects.first()
        self.assertEqual(shift.officer, self.officer)

    def test_super_admin_can_delete_shift(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.super_admin)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Shift.objects.count(), 0)

    # --- Read-Only Fields ---

    def test_cannot_set_expected_cash_manually(self):
        self._auth(self.officer)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '50000.00',
            'expected_cash': '999999.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        shift = Shift.objects.first()
        self.assertIsNone(shift.expected_cash)  # masih open, expected_cash null

    def test_cannot_set_difference_manually(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.officer)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.patch(url, {
            'status': 'closed',
            'closing_cash': '60000.00',
            'difference': '500000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        shift.refresh_from_db()
        # difference tetap dihitung sistem: closing_cash - expected_cash = 60000-50000 = 10000
        self.assertEqual(float(shift.difference), 10000.00)

    def test_cannot_set_closed_at_manually(self):
        shift = Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(self.officer)
        url = reverse('shifts:shift-detail', args=[shift.id])
        resp = self.client.patch(url, {
            'status': 'closed',
            'closing_cash': '60000.00',
            'closed_at': '2020-01-01T00:00:00Z',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        shift.refresh_from_db()
        # closed_at harus timestamp sekarang, bukan 2020
        self.assertEqual(shift.closed_at.year, 2026)

    # --- Unauthenticated ---

    def test_unauthenticated_cannot_access_shifts(self):
        url = reverse('shifts:shift-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Owner ---

    def test_owner_cannot_create_shift(self):
        owner = User.objects.create_user(
            username='owner1', password='pass1234', role='owner',
            tenant=self.tenant, outlet=self.outlet,
        )
        self._auth(owner)
        url = reverse('shifts:shift-list')
        resp = self.client.post(url, {
            'opening_cash': '50000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_list_shifts(self):
        owner = User.objects.create_user(
            username='owner1', password='pass1234', role='owner',
            tenant=self.tenant, outlet=self.outlet,
        )
        Shift.objects.create(
            outlet=self.outlet, officer=self.officer,
            opening_cash=50000, status=Shift.Status.OPEN,
        )
        self._auth(owner)
        url = reverse('shifts:shift-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Owner authenticated tapi bukan officer/admin — get_queryset return none
        # Sesuai ViewSet: hanya officer dapat shift sendiri, admin dapat outlet-nya
        # Owner tidak masuk kondisi manapun → qs.none()
        self.assertEqual(len(resp.data['results']), 0)