"""
Topic 13 — Testing for checkin-service.
13.1 Unit tests  — CheckIn model + serializer
13.2 API tests   — response codes and shape only
13.3 Integration — API + DB together
"""

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
import base64
from .models import CheckIn
from .serializers import CheckInSerializer, ScanRequestSerializer


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def make_employee_payload(user):
    return {
        'user_id':  str(user.id),
        'username': user.username,
        'groups':   ['Employee'],
    }

ADMIN_PAYLOAD = {
    'user_id':  '99',
    'username': 'admin',
    'groups':   ['Administrator'],
}


# ─────────────────────────────────────────────
# 13.1 Unit Tests — CheckIn Model
# ─────────────────────────────────────────────

class CheckInModelTest(TestCase):
    """Unit tests for CheckIn model fields, constraints, and methods."""

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
        """CheckIns can be ordered by most recent first."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=1)
        records = CheckIn.objects.filter(ngo_id=1).order_by('-checked_in_at')
        self.assertEqual(records.count(), 2)


# ─────────────────────────────────────────────
# 13.1 Unit Tests — Serializers
# ─────────────────────────────────────────────

class CheckInSerializerTest(TestCase):
    """Unit tests for CheckIn serializers."""

    def test_serializer_contains_expected_fields(self):
        """Serializer returns all required fields."""
        checkin = CheckIn.objects.create(employee_id=1, ngo_id=1)
        serializer = CheckInSerializer(checkin)
        for field in ['id', 'employee_id', 'ngo_id', 'checked_in_at']:
            self.assertIn(field, serializer.data.keys())

    def test_serializer_data_matches_model(self):
        """Serializer data matches model fields exactly."""
        checkin = CheckIn.objects.create(employee_id=2, ngo_id=3)
        serializer = CheckInSerializer(checkin)
        self.assertEqual(serializer.data['employee_id'], 2)
        self.assertEqual(serializer.data['ngo_id'], 3)
        self.assertIsNotNone(serializer.data['checked_in_at'])

    def test_scan_request_serializer_valid(self):
        """ScanRequestSerializer validates positive ngo_id."""
        serializer = ScanRequestSerializer(data={'ngo_id': 1})
        self.assertTrue(serializer.is_valid())

    def test_scan_request_serializer_invalid_negative(self):
        """ScanRequestSerializer rejects negative ngo_id."""
        serializer = ScanRequestSerializer(data={'ngo_id': -1})
        self.assertFalse(serializer.is_valid())
        self.assertIn('ngo_id', serializer.errors)

    def test_scan_request_serializer_missing_field(self):
        """ScanRequestSerializer rejects empty data."""
        serializer = ScanRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())


# ─────────────────────────────────────────────
# 13.2 API Tests — response codes and shape only
# ─────────────────────────────────────────────

class CheckInAPITest(TestCase):
    """
    Pure API tests — checks HTTP status codes and response shape only.
    Does NOT verify database state changes.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testemployee',
            password='testpass123',
        )
        self.employee_payload = make_employee_payload(self.user)

    # ── scan_checkin ──────────────────────────

    def test_scan_checkin_response_structure(self):
        """Scan response contains required fields."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('checkin', response.data)
        self.assertIn('employee_id', response.data['checkin'])
        self.assertIn('ngo_id', response.data['checkin'])
        self.assertIn('checked_in_at', response.data['checkin'])

    def test_scan_checkin_duplicate_returns_400(self):
        """Second scan by same employee returns 400."""
        self.client.force_authenticate(user=self.employee_payload)
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        response = self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Already checked in', response.data['error'])

    def test_scan_checkin_missing_ngo_id(self):
        """Scan without ngo_id returns 400."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scan_checkin_invalid_ngo_id(self):
        """Scan with negative ngo_id returns 400."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {'ngo_id': -1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ── generate_qr ───────────────────────────

    def test_generate_qr_admin_success(self):
        """Admin can generate QR code and get 200."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_generate_qr_response_structure(self):
        """QR response contains qr_code_base64, scan_url and ngo_id."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertIn('qr_code_base64', response.data)
        self.assertIn('scan_url', response.data)
        self.assertIn('ngo_id', response.data)

    def test_generate_qr_contains_correct_ngo_id(self):
        """QR scan URL contains correct ngo_id."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.data['ngo_id'], 1)
        self.assertIn('ngo_id=1', response.data['scan_url'])

    def test_generate_qr_base64_is_valid_png(self):
        """QR code base64 decodes to valid PNG data."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        decoded = base64.b64decode(response.data['qr_code_base64'])
        self.assertGreater(len(decoded), 0)
        self.assertTrue(decoded[:4] == b'\x89PNG')

    def test_generate_qr_employee_blocked(self):
        """Employee cannot generate QR code — returns 403."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── live_monitor ──────────────────────────

    def test_live_monitor_admin_success(self):
        """Admin can access live monitor and get 200."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_live_monitor_response_structure(self):
        """Live monitor response contains required fields."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertIn('ngo_id', response.data)
        self.assertIn('checked_in_count', response.data)
        self.assertIn('checkins', response.data)
        self.assertEqual(response.data['ngo_id'], 1)

    def test_live_monitor_empty_response(self):
        """Live monitor shows zero count and empty list when no checkins."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.data['checked_in_count'], 0)
        self.assertEqual(response.data['checkins'], [])

    def test_live_monitor_employee_blocked(self):
        """Employee cannot access live monitor — returns 403."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── permissions ───────────────────────────

    def test_unauthenticated_scan_blocked(self):
        """Unauthenticated scan is rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_unauthenticated_qr_blocked(self):
        """Unauthenticated QR generation is rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])

    def test_unauthenticated_monitor_blocked(self):
        """Unauthenticated live monitor access is rejected."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ])


# ─────────────────────────────────────────────
# 13.3 Integration Tests — API + DB together
# ─────────────────────────────────────────────

class CheckinIntegrationTest(TestCase):
    """
    Integration tests — verifies the full chain:
    API request → business logic → database write/read.
    """

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testemployee',
            password='testpass123',
        )
        self.employee_payload = make_employee_payload(self.user)

    # ── scan saves to DB ──────────────────────

    def test_scan_checkin_creates_db_record(self):
        """Successful scan creates exactly one CheckIn record in DB."""
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CheckIn.objects.count(), 1)

    def test_scan_checkin_saves_correct_employee(self):
        """DB record stores the employee_id from the JWT token."""
        self.client.force_authenticate(user=self.employee_payload)
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        checkin = CheckIn.objects.first()
        self.assertEqual(str(checkin.employee_id), self.employee_payload['user_id'])

    def test_scan_checkin_saves_correct_ngo(self):
        """DB record stores the correct ngo_id from the request."""
        self.client.force_authenticate(user=self.employee_payload)
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 5})
        checkin = CheckIn.objects.first()
        self.assertEqual(checkin.ngo_id, 5)

    def test_duplicate_scan_does_not_create_second_record(self):
        """Second scan by same employee does not add a second DB record."""
        self.client.force_authenticate(user=self.employee_payload)
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.assertEqual(CheckIn.objects.count(), 1)

    # ── live monitor reflects DB ──────────────

    def test_live_monitor_count_reflects_db(self):
        """Live monitor count matches actual CheckIn records in DB."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=1)
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.data['checked_in_count'], 2)

    def test_live_monitor_filters_by_ngo(self):
        """Live monitor only returns checkins for the requested NGO."""
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=2)
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.data['checked_in_count'], 1)

    def test_live_monitor_updates_after_new_scan(self):
        """Live monitor count increases after a new scan is submitted."""
        self.client.force_authenticate(user=ADMIN_PAYLOAD)
        before = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(before.data['checked_in_count'], 0)

        CheckIn.objects.create(employee_id=self.user.id, ngo_id=1)

        after = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(after.data['checked_in_count'], 1)

    def test_multiple_employees_same_ngo_all_recorded(self):
        """All employees who scan for the same NGO are saved in DB."""
        user2 = User.objects.create_user('emp2', password='Pass1234')
        user3 = User.objects.create_user('emp3', password='Pass1234')

        for user in [self.user, user2, user3]:
            client = APIClient()
            client.force_authenticate(user=make_employee_payload(user))
            client.post('/api/v1/checkins/scan/', {'ngo_id': 1})

        self.assertEqual(CheckIn.objects.filter(ngo_id=1).count(), 3)