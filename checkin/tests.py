from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
import base64
from .models import CheckIn


# ─────────────────────────────────────────────
# Topic 13.1 — Unit Tests: CheckIn Model
# ─────────────────────────────────────────────

class CheckInModelTest(TestCase):
    """
    Unit tests for the CheckIn model.
    Tests model fields, constraints and methods in isolation.
    """

    def test_checkin_created(self):
        """CheckIn object is created with correct fields."""
        checkin = CheckIn.objects.create(employee_id=1, ngo_id=1)
        self.assertEqual(checkin.employee_id, 1)
        self.assertEqual(checkin.ngo_id, 1)
        self.assertIsNotNone(checkin.checked_in_at)

    def test_checkin_str(self):
        """CheckIn string representation is correct."""
        checkin = CheckIn.objects.create(employee_id=1, ngo_id=1)
        self.assertEqual(str(checkin), "Employee 1 → NGO 1")

    def test_duplicate_checkin_blocked(self):
        """Same employee cannot check in to same NGO twice."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        with self.assertRaises(Exception):
            CheckIn.objects.create(employee_id=1, ngo_id=1)

    def test_different_employee_same_ngo(self):
        """Different employees can check into same NGO."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=1)
        self.assertEqual(CheckIn.objects.count(), 2)

    def test_same_employee_different_ngo(self):
        """Same employee can check into different NGOs."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=1, ngo_id=2)
        self.assertEqual(CheckIn.objects.count(), 2)

    def test_checkin_timestamp_auto_set(self):
        """checked_in_at is automatically set on creation."""
        checkin = CheckIn.objects.create(employee_id=3, ngo_id=1)
        self.assertIsNotNone(checkin.checked_in_at)

    def test_checkin_ordering(self):
        """CheckIns are ordered by most recent first."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=1)
        records = CheckIn.objects.filter(
            ngo_id=1
        ).order_by('-checked_in_at')
        self.assertEqual(records.count(), 2)


# ─────────────────────────────────────────────
# Topic 13.2 + 13.3 — API + Integration Tests
# ─────────────────────────────────────────────

class CheckInAPITest(TestCase):
    """
    Integration tests for CheckIn API endpoints.
    Tests API + database interaction together.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testemployee',
            password='testpass123'
        )
        self.employee_payload = {
            'user_id': str(self.user.id),
            'username': 'testemployee',
            'groups': ['Employee']
        }
        self.admin_payload = {
            'user_id': '99',
            'username': 'admin',
            'groups': ['Administrator']
        }

    # ── scan_checkin ──────────────────────────

    def test_scan_checkin_success(self):
        """Employee successfully checks in via QR scan."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post(
            '/api/v1/checkins/scan/',
            {'ngo_id': 1}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CheckIn.objects.count(), 1)
        self.assertEqual(
            CheckIn.objects.first().employee_id,
            self.user.id
        )

    def test_scan_checkin_response_structure(self):
        """Scan response contains required fields."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post(
            '/api/v1/checkins/scan/',
            {'ngo_id': 1}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('checkin', response.data)
        self.assertIn('employee_id', response.data['checkin'])
        self.assertIn('ngo_id', response.data['checkin'])
        self.assertIn('checked_in_at', response.data['checkin'])

    def test_scan_checkin_duplicate_blocked(self):
        """Second scan by same employee is rejected."""
        self.client.force_authenticate(user=self.employee_payload)
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        response = self.client.post(
            '/api/v1/checkins/scan/',
            {'ngo_id': 1}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Already checked in', response.data['error'])

    def test_scan_checkin_missing_ngo_id(self):
        """Scan without ngo_id returns validation error."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scan_checkin_invalid_ngo_id(self):
        """Scan with negative ngo_id returns validation error."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post(
            '/api/v1/checkins/scan/',
            {'ngo_id': -1}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scan_checkin_saves_correct_employee(self):
        """Checkin record saves employee_id from JWT token."""
        self.client.force_authenticate(user=self.employee_payload)
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        checkin = CheckIn.objects.first()
        self.assertEqual(str(checkin.employee_id), self.employee_payload['user_id'])

    # ── generate_qr ───────────────────────────

    def test_generate_qr_admin_only(self):
        """Admin can generate QR code."""
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_qr_response_structure(self):
        """QR response contains required fields."""
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('qr_code_base64', response.data)
        self.assertIn('scan_url', response.data)
        self.assertIn('ngo_id', response.data)

    def test_generate_qr_contains_correct_ngo_id(self):
        """QR scan URL contains correct ngo_id."""
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.data['ngo_id'], 1)
        self.assertIn('ngo_id=1', response.data['scan_url'])

    def test_generate_qr_base64_is_valid(self):
        """QR code base64 decodes to valid PNG data."""
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        qr_base64 = response.data['qr_code_base64']
        decoded = base64.b64decode(qr_base64)
        self.assertGreater(len(decoded), 0)
        # PNG files start with this magic number
        self.assertTrue(decoded[:4] == b'\x89PNG')

    def test_generate_qr_employee_blocked(self):
        """Employee cannot generate QR code."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── live_monitor ──────────────────────────

    def test_live_monitor_admin_only(self):
        """Admin can access live monitor."""
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_live_monitor_response_structure(self):
        """Live monitor response contains required fields."""
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('ngo_id', response.data)
        self.assertIn('checked_in_count', response.data)
        self.assertIn('checkins', response.data)
        self.assertEqual(response.data['ngo_id'], 1)

    def test_live_monitor_empty(self):
        """Live monitor shows zero when no checkins."""
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.data['checked_in_count'], 0)
        self.assertEqual(response.data['checkins'], [])

    def test_live_monitor_returns_correct_count(self):
        """Live monitor count matches actual checkins in DB."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=1)
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.data['checked_in_count'], 2)

    def test_live_monitor_filters_by_ngo(self):
        """Live monitor only shows checkins for specified NGO."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=2)
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.data['checked_in_count'], 1)

    def test_live_monitor_employee_blocked(self):
        """Employee cannot access live monitor."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── permissions ───────────────────────────

    def test_unauthenticated_scan_blocked(self):
        """Unauthenticated scan request is rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            '/api/v1/checkins/scan/',
            {'ngo_id': 1}
        )
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])

    def test_unauthenticated_qr_blocked(self):
        """Unauthenticated QR generation is rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])

    def test_unauthenticated_monitor_blocked(self):
        """Unauthenticated live monitor access is rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])