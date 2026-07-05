from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    """Test health check endpoint."""

    def test_health_returns_200_and_ok_status(self):
        """Endpoint /api/health/ returns 200 with status ok."""
        response = self.client.get(reverse('health-check'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'ok')

    def test_health_returns_json_with_required_fields(self):
        """Response contains status, database, timestamp fields."""
        response = self.client.get(reverse('health-check'))
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('database', data)
        self.assertIn('timestamp', data)

    def test_health_database_connected(self):
        """Database status is 'connected' under normal conditions."""
        response = self.client.get(reverse('health-check'))
        self.assertEqual(response.json()['database'], 'connected')

    def test_health_no_auth_required(self):
        """Endpoint is accessible without authentication."""
        response = self.client.get(reverse('health-check'))
        self.assertEqual(response.status_code, 200)

    def test_health_not_throttled(self):
        """Multiple rapid requests to health check are not rate-limited."""
        for _ in range(20):
            response = self.client.get(reverse('health-check'))
            self.assertEqual(response.status_code, 200)