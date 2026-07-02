from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, Tenant, Outlet
from packages.models import Package


class PackageAPITests(TestCase):
    """Test CRUD Package via API as Admin & Super Admin."""

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

    # --- List / Read ---

    def test_list_packages_as_admin(self):
        Package.objects.create(
            outlet=self.outlet, name='Happy Hour',
            type=Package.PackageType.HAPPY_HOUR,
            duration_minutes=60, fixed_price=50000,
        )
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)

    def test_retrieve_package_as_admin(self):
        pkg = Package.objects.create(
            outlet=self.outlet, name='Fixed 2h',
            type=Package.PackageType.FIXED_DURATION,
            duration_minutes=120, fixed_price=80000,
        )
        self._auth(self.admin)
        url = reverse('packages:package-detail', args=[pkg.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['name'], 'Fixed 2h')

    # --- Create ---

    def test_create_fixed_duration_package(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': '2 Hour',
            'type': 'fixed_duration',
            'duration_minutes': 120,
            'fixed_price': '80000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Package.objects.count(), 1)
        pkg = Package.objects.first()
        self.assertEqual(pkg.outlet, self.outlet)
        self.assertEqual(pkg.type, Package.PackageType.FIXED_DURATION)

    def test_create_per_minute_package(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Per Minute Rate',
            'type': 'per_minute',
            'price_per_minute': '500.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pkg = Package.objects.first()
        self.assertEqual(pkg.price_per_minute, 500)

    def test_create_open_loss_package(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Open Loss',
            'type': 'open_loss',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pkg = Package.objects.first()
        self.assertIsNone(pkg.duration_minutes)
        self.assertIsNone(pkg.fixed_price)

    def test_create_happy_hour_package(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Happy Hour',
            'type': 'happy_hour',
            'duration_minutes': 60,
            'fixed_price': '50000.00',
            'valid_start_time': '14:00:00',
            'valid_end_time': '17:00:00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        pkg = Package.objects.first()
        self.assertEqual(pkg.type, Package.PackageType.HAPPY_HOUR)

    # --- Update ---

    def test_update_package_as_admin(self):
        pkg = Package.objects.create(
            outlet=self.outlet, name='Old Name',
            type=Package.PackageType.FIXED_DURATION,
            duration_minutes=90, fixed_price=60000,
        )
        self._auth(self.admin)
        url = reverse('packages:package-detail', args=[pkg.id])
        resp = self.client.patch(url, {'name': 'New Name'})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        pkg.refresh_from_db()
        self.assertEqual(pkg.name, 'New Name')

    # --- Delete ---

    def test_delete_package_as_admin(self):
        pkg = Package.objects.create(
            outlet=self.outlet, name='To Delete',
            type=Package.PackageType.PER_MINUTE,
            price_per_minute=300,
        )
        self._auth(self.admin)
        url = reverse('packages:package-detail', args=[pkg.id])
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Package.objects.count(), 0)

    # --- Super Admin ---

    def test_super_admin_can_see_all_outlets(self):
        other_tenant = Tenant.objects.create(name='Other', code='OT')
        other_outlet = Outlet.objects.create(tenant=other_tenant, name='Other Outlet', code='OO')
        Package.objects.create(
            outlet=self.outlet, name='Pkg A',
            type=Package.PackageType.PER_MINUTE, price_per_minute=100,
        )
        Package.objects.create(
            outlet=other_outlet, name='Pkg B',
            type=Package.PackageType.PER_MINUTE, price_per_minute=200,
        )
        self._auth(self.super_admin)
        url = reverse('packages:package-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 2)

    # --- Unique Constraint ---

    def test_create_duplicate_package_name_fails(self):
        Package.objects.create(
            outlet=self.outlet, name='Unique',
            type=Package.PackageType.PER_MINUTE, price_per_minute=100,
        )
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Unique',
            'type': 'per_minute',
            'price_per_minute': '200.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Validation: Type-specific ---

    def test_fixed_duration_requires_duration(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Bad Fixed',
            'type': 'fixed_duration',
            'fixed_price': '10000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration_minutes', resp.data)

    def test_fixed_duration_requires_fixed_price(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Bad Fixed 2',
            'type': 'fixed_duration',
            'duration_minutes': 60,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fixed_price', resp.data)

    def test_per_minute_requires_price_per_minute(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Bad Per Min',
            'type': 'per_minute',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price_per_minute', resp.data)

    def test_open_loss_rejects_duration_and_fixed_price(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Bad Open',
            'type': 'open_loss',
            'duration_minutes': 60,
            'fixed_price': '50000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration_minutes', resp.data)
        self.assertIn('fixed_price', resp.data)

    def test_happy_hour_requires_duration_and_fixed_price(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Bad Happy',
            'type': 'happy_hour',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration_minutes', resp.data)
        self.assertIn('fixed_price', resp.data)

    # --- Validation: Day Type ---

    def test_specific_day_requires_date(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Specific No Date',
            'type': 'fixed_duration',
            'duration_minutes': 60,
            'fixed_price': '50000.00',
            'valid_day_type': 'specific_day',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('specific_date', resp.data)

    def test_non_specific_day_rejects_date(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Extra Date',
            'type': 'fixed_duration',
            'duration_minutes': 60,
            'fixed_price': '50000.00',
            'valid_day_type': 'all',
            'specific_date': '2026-01-01',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('specific_date', resp.data)

    # --- Validation: Time Range ---

    def test_end_time_must_be_after_start_time(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Bad Time',
            'type': 'happy_hour',
            'duration_minutes': 60,
            'fixed_price': '50000.00',
            'valid_start_time': '17:00:00',
            'valid_end_time': '14:00:00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('valid_end_time', resp.data)

    # --- Validation: Numeric ---

    def test_duration_must_be_positive(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Negative Duration',
            'type': 'fixed_duration',
            'duration_minutes': 0,
            'fixed_price': '50000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration_minutes', resp.data)

    def test_fixed_price_must_be_positive(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Negative Price',
            'type': 'fixed_duration',
            'duration_minutes': 60,
            'fixed_price': '-1000.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fixed_price', resp.data)

    def test_price_per_minute_must_be_positive(self):
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.post(url, {
            'outlet': self.outlet.id,
            'name': 'Negative PPM',
            'type': 'per_minute',
            'price_per_minute': '-50.00',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('price_per_minute', resp.data)

    # --- Outlet Scoping ---

    def test_admin_cannot_see_other_outlet_packages(self):
        other_tenant = Tenant.objects.create(name='Other', code='OT')
        other_outlet = Outlet.objects.create(tenant=other_tenant, name='Other Outlet', code='OO')
        Package.objects.create(
            outlet=self.outlet, name='Mine',
            type=Package.PackageType.PER_MINUTE, price_per_minute=100,
        )
        Package.objects.create(
            outlet=other_outlet, name='Theirs',
            type=Package.PackageType.PER_MINUTE, price_per_minute=200,
        )
        self._auth(self.admin)
        url = reverse('packages:package-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['results']), 1)
        self.assertEqual(resp.data['results'][0]['name'], 'Mine')