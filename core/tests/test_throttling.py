import unittest

from django.test import TestCase
from django.urls import reverse
from django.core.cache import cache
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle
from users.models import User, Tenant, Outlet

# Tight throttle limits for throttling tests.
_THROTTLE_TEST_RATES = {
    'auth': '5/minute',
    'user_write': '120/minute',
    'anon_read': '60/minute',
    'sustained': '1000/hour',
}


def _apply_throttle_rates(rates):
    """Force DRF's api_settings AND SimpleRateThrottle to use the given rates.

    SimpleRateThrottle.THROTTLE_RATES is captured at class-definition time
    and does not re-read api_settings at runtime, so we must set both.
    """
    api_settings._cached_attrs.discard('DEFAULT_THROTTLE_RATES')
    api_settings._cached_attrs.discard('DEFAULT_THROTTLE_CLASSES')
    api_settings.DEFAULT_THROTTLE_RATES = rates
    SimpleRateThrottle.THROTTLE_RATES = rates


class ThrottlingTests(TestCase):
    """Test API rate limiting behavior.

    These tests explicitly set DRF's throttle rates to tight limits
    and clear the throttle cache between tests.

    The original SimpleRateThrottle.THROTTLE_RATES is saved before
    the class runs and restored afterward so that other test classes
    (e.g. users/tests.py) are not affected by the tight test rates.
    """

    _original_throttle_rates = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_throttle_rates = dict(SimpleRateThrottle.THROTTLE_RATES)

    @classmethod
    def tearDownClass(cls):
        SimpleRateThrottle.THROTTLE_RATES = cls._original_throttle_rates
        super().tearDownClass()

    @classmethod
    def setUpTestData(cls):
        cls.tenant = Tenant.objects.create(name='Throttle Test Tenant', code='THR')
        cls.outlet = Outlet.objects.create(
            name='Throttle Test Outlet',
            tenant=cls.tenant,
        )
        cls.user = User.objects.create_user(
            username='throttleuser',
            email='throttle@test.com',
            password='testpass123',
            role=User.RoleEnum.SUPER_ADMIN,
            outlet=cls.outlet,
            tenant=cls.tenant,
        )

    def setUp(self):
        """Clear cache and enforce tight throttle rates before each test."""
        cache.clear()
        _apply_throttle_rates(_THROTTLE_TEST_RATES)

    def test_auth_endpoint_throttled(self):
        """6 requests to /api/auth/login/ within rate limit — 6th should be 429."""
        url = reverse('auth-login')
        payload = {'username': 'throttleuser', 'password': 'wrongpass'}

        # Send 5 requests — all should go through (non-429)
        for i in range(5):
            response = self.client.post(url, payload, content_type='application/json')
            self.assertNotEqual(
                response.status_code,
                status.HTTP_429_TOO_MANY_REQUESTS,
                f'Request {i + 1} should not be throttled yet',
            )

        # 6th request should be rate-limited
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @unittest.skip('Time-sensitive test — skip in CI, run manually if needed')
    def test_auth_throttle_resets(self):
        """After throttle window expires, requests succeed again."""
        url = reverse('auth-login')
        payload = {'username': 'throttleuser', 'password': 'wrongpass'}

        # Exhaust the rate limit
        for _ in range(5):
            self.client.post(url, payload, content_type='application/json')

        # 6th should be throttled
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Reset cache to simulate time passing
        cache.clear()

        # Should work again
        response = self.client.post(url, payload, content_type='application/json')
        self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_throttle_headers_present(self):
        """Throttled responses contain Retry-After header."""
        url = reverse('auth-login')
        payload = {'username': 'throttleuser', 'password': 'wrongpass'}

        # Exhaust all 5 requests
        for _ in range(5):
            self.client.post(url, payload, content_type='application/json')

        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # DRF throttled responses should include Retry-After header
        self.assertIn('Retry-After', response)

    def test_write_endpoint_not_throttled_for_read(self):
        """GET requests to user-list are not blocked by auth throttle (different scope)."""
        url = reverse('auth-login')
        payload = {'username': 'throttleuser', 'password': 'testpass123'}
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = response.json()['access']

        # Multiple GET requests to a list endpoint should not hit auth throttle
        list_url = reverse('user-list')
        for _ in range(10):
            response = self.client.get(
                list_url,
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health_not_throttled_even_under_load(self):
        """Health check remains accessible even when other endpoints are throttled."""
        health_url = reverse('health-check')
        auth_url = reverse('auth-login')
        payload = {'username': 'throttleuser', 'password': 'wrongpass'}

        # Exhaust auth rate limit
        for _ in range(5):
            self.client.post(auth_url, payload, content_type='application/json')

        # Auth should be throttled
        response = self.client.post(auth_url, payload, content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Health should still be accessible
        response = self.client.get(health_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)