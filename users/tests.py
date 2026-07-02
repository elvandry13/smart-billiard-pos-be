"""
Unit test untuk app users: model, auth, JWT, viewset, permission, dan custom actions.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import User, Tenant, Outlet, Role, Permission


# ──────────────────────────────────────────────
# Model Tests
# ──────────────────────────────────────────────

class UserModelTest(TestCase):
    """Test custom User model, manager, dan constraint."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Test Tenant', code='TT')
        cls.outlet = Outlet.objects.create(
            name='Test Outlet', code='TO', tenant=cls.tenant, timezone='Asia/Jakarta'
        )

    def test_create_super_admin(self):
        u = User.objects.create_user(
            username='sa', email='sa@test.com', password='pass',
            role=User.RoleEnum.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        self.assertEqual(u.role, User.RoleEnum.SUPER_ADMIN)
        self.assertIsNone(u.tenant)
        self.assertIsNone(u.outlet)

    def test_create_owner(self):
        u = User.objects.create_user(
            username='owner', email='o@test.com', password='pass',
            role=User.RoleEnum.OWNER, tenant=self.tenant,
        )
        self.assertEqual(u.role, User.RoleEnum.OWNER)
        self.assertIsNotNone(u.tenant)
        self.assertIsNone(u.outlet)

    def test_create_admin(self):
        u = User.objects.create_user(
            username='admin', email='a@test.com', password='pass',
            role=User.RoleEnum.ADMIN, tenant=self.tenant, outlet=self.outlet,
        )
        self.assertEqual(u.role, User.RoleEnum.ADMIN)
        self.assertIsNotNone(u.tenant)
        self.assertIsNotNone(u.outlet)

    def test_create_officer(self):
        u = User.objects.create_user(
            username='officer', email='of@test.com', password='pass',
            role=User.RoleEnum.OFFICER, tenant=self.tenant, outlet=self.outlet,
        )
        self.assertEqual(u.role, User.RoleEnum.OFFICER)

    def test_user_str(self):
        u = User.objects.create_user(
            username='testuser', email='tu@test.com', password='pass',
            role=User.RoleEnum.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        # __str__ mengembalikan format 'username (role_display)'
        self.assertIn('testuser', str(u))

    def test_create_superuser_command(self):
        u = User.objects.create_superuser('boss', 'boss@test.com', 'pass')
        self.assertTrue(u.is_staff)
        self.assertTrue(u.is_superuser)
        self.assertEqual(u.role, User.RoleEnum.SUPER_ADMIN)

    def test_user_without_username_raises(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(username='', email='a@b.com', password='pass')


class RolePermissionModelTest(TestCase):
    """Test model Role dan Permission serta M2M."""

    def test_role_str(self):
        r = Role.objects.create(name='test_role')
        self.assertEqual(str(r), 'test_role')

    def test_permission_str(self):
        p = Permission.objects.create(name='Test Perm', codename='test_perm')
        self.assertEqual(str(p), 'Test Perm')

    def test_role_permission_m2m(self):
        p1 = Permission.objects.create(name='P1', codename='p1')
        p2 = Permission.objects.create(name='P2', codename='p2')
        r = Role.objects.create(name='test_role')
        r.permissions.set([p1, p2])
        self.assertEqual(r.permissions.count(), 2)
        self.assertIn(p1, r.permissions.all())


# ──────────────────────────────────────────────
# Auth & ViewSet Tests (API)
# ──────────────────────────────────────────────

class AuthAPITest(APITestCase):
    """Test endpoint login, logout, refresh, dan change-password."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='T1', code='T1')
        cls.outlet = Outlet.objects.create(
            name='O1', code='O1', tenant=cls.tenant, timezone='Asia/Jakarta'
        )
        cls.user = User.objects.create_user(
            username='officer1', email='of1@test.com', password='officerpass',
            role=User.RoleEnum.OFFICER, tenant=cls.tenant, outlet=cls.outlet,
        )

    def _login(self, username='officer1', password='officerpass'):
        return self.client.post(reverse('auth-login'), {
            'username': username, 'password': password,
        }, format='json')

    def test_login_success(self):
        resp = self._login()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_login_invalid_credentials(self):
        resp = self._login(password='wrong')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        login_resp = self._login()
        refresh = login_resp.data['refresh']
        resp = self.client.post(reverse('auth-refresh'), {'refresh': refresh}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)

    def test_logout_blacklists_refresh(self):
        login_resp = self._login()
        access = login_resp.data['access']
        refresh = login_resp.data['refresh']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        resp = self.client.post(reverse('auth-logout'), {'refresh': refresh}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Token sudah di-blacklist → refresh harus ditolak
        resp2 = self.client.post(reverse('auth-refresh'), {'refresh': refresh}, format='json')
        # Expected: 401 (token tidak valid) atau 400 (token sudah di-blacklist oleh SimpleJWT)
        self.assertIn(resp2.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_400_BAD_REQUEST])

    def test_change_password(self):
        login_resp = self._login()
        access = login_resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        resp = self.client.put(reverse('auth-password-change'), {
            'old_password': 'officerpass',
            'new_password': 'NewPass123!',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Login ulang dengan password baru
        resp_new = self._login(password='NewPass123!')
        self.assertEqual(resp_new.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old(self):
        login_resp = self._login()
        access = login_resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        resp = self.client.put(reverse('auth-password-change'), {
            'old_password': 'wrongold',
            'new_password': 'NewPass123!',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_authenticated(self):
        login_resp = self._login()
        access = login_resp.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['username'], 'officer1')

    def test_profile_unauthenticated(self):
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class TenantOutLetViewSetTest(APITestCase):
    """Test CRUD Tenant & Outlet hanya untuk Super Admin."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='T1', code='T1')
        cls.superadmin = User.objects.create_user(
            username='sa', email='sa@test.com', password='pass',
            role=User.RoleEnum.SUPER_ADMIN, is_staff=True, is_superuser=True,
        )
        cls.owner = User.objects.create_user(
            username='owner', email='o@test.com', password='pass',
            role=User.RoleEnum.OWNER, tenant=cls.tenant,
        )

    def _auth(self, user):
        resp = self.client.post(reverse('auth-login'), {
            'username': user.username, 'password': 'pass',
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')

    def test_superadmin_list_tenants(self):
        self._auth(self.superadmin)
        resp = self.client.get(reverse('tenant-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # With pagination, resp.data has 'results' key
        data = resp.data.get('results', resp.data)
        names = [t['name'] for t in data]
        self.assertIn('T1', names)

    def test_owner_cannot_list_tenants(self):
        self._auth(self.owner)
        resp = self.client.get(reverse('tenant-list'))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_superadmin_create_tenant(self):
        self._auth(self.superadmin)
        resp = self.client.post(reverse('tenant-list'), {
            'name': 'T2', 'code': 'T2',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Tenant.objects.filter(code='T2').exists())

    def test_superadmin_create_outlet(self):
        self._auth(self.superadmin)
        resp = self.client.post(reverse('outlet-list'), {
            'name': 'Outlet Baru',
            'code': 'OB',
            'tenant': self.tenant.id,
            'timezone': 'Asia/Jakarta',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Outlet.objects.filter(code='OB').exists())


class UserViewSetPermissionTest(APITestCase):
    """Test bahwa Admin hanya bisa CRUD user dalam outlet-nya."""

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='T1', code='T1')
        cls.outlet1 = Outlet.objects.create(
            name='O1', code='O1', tenant=cls.tenant, timezone='Asia/Jakarta'
        )
        cls.outlet2 = Outlet.objects.create(
            name='O2', code='O2', tenant=cls.tenant, timezone='Asia/Makassar'
        )
        cls.admin1 = User.objects.create_user(
            username='admin1', email='a1@test.com', password='pass',
            role=User.RoleEnum.ADMIN, tenant=cls.tenant, outlet=cls.outlet1,
        )
        cls.officer1 = User.objects.create_user(
            username='officer1', email='of1@test.com', password='pass',
            role=User.RoleEnum.OFFICER, tenant=cls.tenant, outlet=cls.outlet1,
        )
        cls.officer2 = User.objects.create_user(
            username='officer2', email='of2@test.com', password='pass',
            role=User.RoleEnum.OFFICER, tenant=cls.tenant, outlet=cls.outlet2,
        )

    def _auth(self, user):
        resp = self.client.post(reverse('auth-login'), {
            'username': user.username, 'password': 'pass',
        }, format='json')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {resp.data["access"]}')

    def test_admin_sees_only_outlet_users(self):
        self._auth(self.admin1)
        resp = self.client.get(reverse('user-list'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # With pagination, resp.data has 'results' key
        data = resp.data.get('results', resp.data)
        usernames = [u['username'] for u in data]
        self.assertIn('officer1', usernames)
        self.assertNotIn('officer2', usernames)

    def test_admin_cannot_promote_to_superadmin(self):
        self._auth(self.admin1)
        resp = self.client.post(reverse('user-list'), {
            'username': 'newuser',
            'email': 'nu@test.com',
            'password': 'SomePass123!',
            'role': User.RoleEnum.SUPER_ADMIN,
            'tenant': self.tenant.id,
            'outlet': self.outlet1.id,
        }, format='json')
        # perform_create now validates role → should return 403
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_create_officer_in_own_outlet(self):
        self._auth(self.admin1)
        resp = self.client.post(reverse('user-list'), {
            'username': 'newofficer',
            'email': 'no@test.com',
            'password': 'SomePass123!',
            'role': User.RoleEnum.OFFICER,
            'tenant': self.tenant.id,
            'outlet': self.outlet1.id,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        u = User.objects.get(username='newofficer')
        self.assertEqual(u.role, User.RoleEnum.OFFICER)
        self.assertEqual(u.outlet, self.outlet1)

    def test_officer_cannot_see_user_list(self):
        self._auth(self.officer1)
        resp = self.client.get(reverse('user-list'))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)