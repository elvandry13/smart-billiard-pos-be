from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, Tenant, Outlet
from tables.models import TableType, Table, PricingRule, AdditionalFee


class TableTypeAPITests(TestCase):
    """Test CRUD TableType via API as Admin & Super Admin."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet = Outlet.objects.create(tenant=cls.tenant, name='Test Outlet', code='TO')
        cls.admin = User.objects.create_user(
            username='admin1', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.super_admin = User.objects.create_superuser(
            username='super', password='pass1234',
        )

    def setUp(self):
        self.client = APIClient()

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_list_table_types_as_admin(self):
        TableType.objects.create(outlet=self.outlet, name='Standard')
        self._auth(self.admin)
        url = reverse('tables:tabletype-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_create_table_type_as_admin(self):
        self._auth(self.admin)
        url = reverse('tables:tabletype-list')
        resp = self.client.post(url, {'name': 'VIP', 'outlet': self.outlet.id}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TableType.objects.count(), 1)
        self.assertEqual(TableType.objects.first().outlet, self.outlet)

    def test_update_table_type_as_admin(self):
        tt = TableType.objects.create(outlet=self.outlet, name='Old')
        self._auth(self.admin)
        url = reverse('tables:tabletype-detail', args=[tt.id])
        resp = self.client.patch(url, {'name': 'New'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        tt.refresh_from_db()
        self.assertEqual(tt.name, 'New')

    def test_delete_table_type_as_admin(self):
        tt = TableType.objects.create(outlet=self.outlet, name='Del')
        self._auth(self.admin)
        url = reverse('tables:tabletype-detail', args=[tt.id])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(TableType.objects.count(), 0)

    def test_super_admin_can_see_all_outlets(self):
        other_tenant = Tenant.objects.create(name='Other', code='OT')
        other_outlet = Outlet.objects.create(tenant=other_tenant, name='Other Outlet', code='OO')
        TableType.objects.create(outlet=self.outlet, name='A')
        TableType.objects.create(outlet=other_outlet, name='B')
        self._auth(self.super_admin)
        url = reverse('tables:tabletype-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 2)


class TableAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Tenant', code='TN')
        cls.outlet = Outlet.objects.create(tenant=cls.tenant, name='Outlet', code='OT')
        cls.tt = TableType.objects.create(outlet=cls.outlet, name='Reguler')
        cls.admin = User.objects.create_user(
            username='admin', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_create_table(self):
        url = reverse('tables:table-list')
        resp = self.client.post(url, {
            'name': 'Meja 1',
            'table_type': self.tt.id,
            'outlet': self.outlet.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Table.objects.first().status, Table.Status.AVAILABLE)

    def test_create_duplicate_table_name_fails(self):
        Table.objects.create(outlet=self.outlet, name='Meja 1', table_type=self.tt)
        url = reverse('tables:table-list')
        resp = self.client.post(url, {
            'name': 'Meja 1',
            'table_type': self.tt.id,
            'outlet': self.outlet.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class PricingRuleAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Tenant', code='TN')
        cls.outlet = Outlet.objects.create(tenant=cls.tenant, name='Outlet', code='OT')
        cls.tt = TableType.objects.create(outlet=cls.outlet, name='VIP')
        cls.admin = User.objects.create_user(
            username='admin', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_create_pricing_rule(self):
        url = reverse('tables:pricingrule-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'table_type': self.tt.id,
            'name': 'Weekday Normal',
            'day_type': 'weekday',
            'start_time': '10:00:00',
            'end_time': '18:00:00',
            'price_per_minute': '500.00',
            'priority': 1,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PricingRule.objects.count(), 1)

    def test_specific_day_requires_date(self):
        url = reverse('tables:pricingrule-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Holiday Rate',
            'day_type': 'specific_day',
            'start_time': '10:00:00',
            'end_time': '22:00:00',
            'price_per_minute': '1000.00',
            'priority': 2,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('specific_date', resp.data)


class AdditionalFeeAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Tenant', code='TN')
        cls.outlet = Outlet.objects.create(tenant=cls.tenant, name='Outlet', code='OT')
        cls.admin = User.objects.create_user(
            username='admin', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_create_additional_fee(self):
        url = reverse('tables:additionalfee-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Service Fee',
            'type': 'percentage',
            'value': '10.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AdditionalFee.objects.count(), 1)

    def test_negative_value_rejected(self):
        url = reverse('tables:additionalfee-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Bad Fee',
            'type': 'fixed',
            'value': '-5.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)