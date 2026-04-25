from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status
from .models import CheckIn


class CheckInModelTest(TestCase):
    """Topic 13.1 — Unit Testing: Model"""

    def test_checkin_created(self):
        checkin = CheckIn.objects.create(
            employee_id=1,
            ngo_id=1
        )
        self.assertEqual(checkin.employee_id, 1)
        self.assertEqual(checkin.ngo_id, 1)
        self.assertIsNotNone(checkin.checked_in_at)

    def test_checkin_str(self):
        checkin = CheckIn.objects.create(
            employee_id=1,
            ngo_id=1
        )
        self.assertEqual(str(checkin), "Employee 1 → NGO 1")

    def test_duplicate_checkin_blocked(self):
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        with self.assertRaises(Exception):
            CheckIn.objects.create(employee_id=1, ngo_id=1)

    def test_different_employee_same_ngo(self):
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=1)
        self.assertEqual(CheckIn.objects.count(), 2)

    def test_same_employee_different_ngo(self):
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=1, ngo_id=2)
        self.assertEqual(CheckIn.objects.count(), 2)


class CheckInAPITest(TestCase):
    """Topic 13.3 — Integration Testing: API + Database"""

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

    def test_scan_checkin_success(self):
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {
            'ngo_id': 1
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CheckIn.objects.count(), 1)

    def test_scan_checkin_duplicate_blocked(self):
        self.client.force_authenticate(user=self.employee_payload)
        self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        response = self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Already checked in', response.data['error'])

    def test_scan_checkin_missing_ngo_id(self):
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_scan_checkin_invalid_ngo_id(self):
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.post('/api/v1/checkins/scan/', {
            'ngo_id': -1
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_live_monitor_admin_only(self):
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('checkins', response.data)
        self.assertIn('checked_in_count', response.data)

    def test_live_monitor_employee_blocked(self):
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_live_monitor_returns_correct_count(self):
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=1)
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['checked_in_count'], 2)

    def test_live_monitor_empty(self):
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['checked_in_count'], 0)
        self.assertEqual(response.data['checkins'], [])

    def test_live_monitor_different_ngo(self):
        CheckIn.objects.create(employee_id=1, ngo_id=1)
        CheckIn.objects.create(employee_id=2, ngo_id=2)
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/live-monitor/1/')
        self.assertEqual(response.data['checked_in_count'], 1)

    def test_unauthenticated_scan_blocked(self):
        self.client.force_authenticate(user=None)
        response = self.client.post('/api/v1/checkins/scan/', {'ngo_id': 1})
        self.assertIn(response.status_code, [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN
        ])

    def test_generate_qr_admin_only(self):
        self.client.force_authenticate(user=self.admin_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('qr_code_base64', response.data)
        self.assertIn('scan_url', response.data)
        self.assertIn('ngo_id', response.data)

    def test_generate_qr_employee_blocked(self):
        self.client.force_authenticate(user=self.employee_payload)
        response = self.client.get('/api/v1/checkins/generate-qr/1/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)