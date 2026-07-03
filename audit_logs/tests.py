"""Unit test untuk app audit_logs: service dan API."""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, Tenant, Outlet
from audit_logs.models import AuditLog
from audit_logs.services import AuditService


class AuditServiceTests(TestCase):
    """Test AuditService.log() — unit test tanpa API."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet = Outlet.objects.create(
            tenant=cls.tenant, name='Test Outlet', code='TO',
        )
        cls.admin = User.objects.create_user(
            username='admin1', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )

    def test_log_creates_entry(self):
        AuditService.log(
            user_id=self.admin.id,
            outlet_id=self.outlet.id,
            action='create',
            object_type='PricingRule',
            object_id=42,
            changes={'price': {'old': 10000, 'new': 15000}},
        )
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_log_all_fields_correct(self):
        entry = AuditService.log(
            user_id=self.admin.id,
            outlet_id=self.outlet.id,
            action='cancel_session',
            object_type='PlaySession',
            object_id=99,
            changes={},
            notes='Customer request',
        )
        self.assertEqual(entry.user, self.admin)
        self.assertEqual(entry.outlet, self.outlet)
        self.assertEqual(entry.action, 'cancel_session')
        self.assertEqual(entry.object_type, 'PlaySession')
        self.assertEqual(entry.object_id, 99)
        self.assertEqual(entry.changes, {})
        self.assertEqual(entry.notes, 'Customer request')
        self.assertIsNotNone(entry.created_at)

    def test_log_nonexistent_user(self):
        entry = AuditService.log(
            user_id=99999,
            outlet_id=self.outlet.id,
            action='update',
            object_type='Package',
            object_id=1,
        )
        self.assertIsNone(entry.user)
        self.assertEqual(AuditLog.objects.count(), 1)

    def test_log_none_outlet(self):
        entry = AuditService.log(
            user_id=self.admin.id,
            outlet_id=None,
            action='open_shift',
            object_type='Shift',
            object_id=1,
        )
        self.assertIsNone(entry.outlet)
        self.assertEqual(AuditLog.objects.count(), 1)


class AuditLogAPITests(TestCase):
    """Test AuditLog API — read-only, scoping, filtering."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet = Outlet.objects.create(
            tenant=cls.tenant, name='Test Outlet', code='TO',
        )
        cls.other_tenant = Tenant.objects.create(name='Other Tenant', code='OT')
        cls.other_outlet = Outlet.objects.create(
            tenant=cls.other_tenant, name='Other Outlet', code='OO',
        )
        cls.admin = User.objects.create_user(
            username='admin1', password='pass1234', role='admin',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.other_admin = User.objects.create_user(
            username='admin2', password='pass1234', role='admin',
            tenant=cls.other_tenant, outlet=cls.other_outlet,
        )
        cls.officer = User.objects.create_user(
            username='officer1', password='pass1234', role='officer',
            tenant=cls.tenant, outlet=cls.outlet,
        )
        cls.super_admin = User.objects.create_superuser(
            username='super', password='pass1234',
        )
        # Buat beberapa audit log
        cls.log1 = AuditLog.objects.create(
            user=cls.admin, outlet=cls.outlet,
            action='cancel_session', object_type='PlaySession', object_id=1,
            notes='Cancel reason A',
        )
        cls.log2 = AuditLog.objects.create(
            user=cls.admin, outlet=cls.outlet,
            action='open_shift', object_type='Shift', object_id=10,
        )
        cls.log3 = AuditLog.objects.create(
            user=cls.other_admin, outlet=cls.other_outlet,
            action='create', object_type='PricingRule', object_id=5,
        )

    def setUp(self):
        self.client = APIClient()
        self.list_url = reverse('auditlog-list')

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def test_admin_can_list_own_outlet(self):
        self._auth(self.admin)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Admin hanya lihat log outlet-nya (log1, log2)
        self.assertEqual(resp.data['count'], 2)

    def test_admin_cannot_see_other_outlet(self):
        self._auth(self.admin)
        resp = self.client.get(self.list_url)
        ids = [item['id'] for item in resp.data['results']]
        self.assertNotIn(self.log3.id, ids)

    def test_officer_cannot_access(self):
        self._auth(self.officer)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_super_admin_can_see_all(self):
        self._auth(self.super_admin)
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 3)

    def test_filter_by_action(self):
        self._auth(self.super_admin)
        resp = self.client.get(self.list_url, {'action': 'cancel_session'})
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['results'][0]['action'], 'cancel_session')

    def test_filter_by_user(self):
        self._auth(self.super_admin)
        resp = self.client.get(self.list_url, {'user': self.admin.id})
        self.assertEqual(resp.data['count'], 2)

    def test_filter_by_object_type(self):
        self._auth(self.super_admin)
        resp = self.client.get(self.list_url, {'object_type': 'PricingRule'})
        self.assertEqual(resp.data['count'], 1)

    def test_retrieve_single_log(self):
        self._auth(self.admin)
        url = reverse('auditlog-detail', args=[self.log1.id])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['action'], 'cancel_session')
        self.assertEqual(resp.data['notes'], 'Cancel reason A')

    def test_unauth_cannot_access(self):
        resp = self.client.get(self.list_url)
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)