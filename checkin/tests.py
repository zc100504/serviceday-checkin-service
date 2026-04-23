from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth.models import User
from unittest.mock import patch
import jwt
import datetime
from django.conf import settings

from checkin.models import CheckIn
from checkin.views import generate_token, decode_token


class CheckinUnitTest(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            username='user', password='pass'
        )

        self.admin = User.objects.create_superuser(
            username='admin', password='pass'
        )

    # ─────────────────────────────
    # TOKEN TESTS
    # ─────────────────────────────
    def test_generate_and_decode_token(self):
        token = generate_token(1, 10)
        payload, error = decode_token(token)

        self.assertIsNone(error)
        self.assertEqual(payload['employee_id'], 1)
        self.assertEqual(payload['ngo_id'], 10)

    def test_decode_invalid_token(self):
        payload, error = decode_token("invalid.token")

        self.assertIsNone(payload)
        self.assertEqual(error, 'Invalid QR code.')

    # ─────────────────────────────
    # GENERATE QR
    # ─────────────────────────────
    def test_generate_qr_success(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/v1/checkins/generate-qr/10/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('qr_code_base64', response.data)
        self.assertIn('token', response.data)

    def test_generate_qr_already_checked_in(self):
        self.client.force_authenticate(user=self.user)

        CheckIn.objects.create(employee_id=self.user.id, ngo_id=10)

        response = self.client.get('/api/v1/checkins/generate-qr/10/')

        self.assertEqual(response.status_code, 400)

    # ─────────────────────────────
    # SCAN CHECKIN
    # ─────────────────────────────
    def test_scan_missing_token(self):
        response = self.client.post('/api/v1/checkins/scan/', {})

        self.assertEqual(response.status_code, 400)

    def test_scan_invalid_token(self):
        response = self.client.post('/api/v1/checkins/scan/', {
            'token': 'invalid'
        })

        self.assertEqual(response.status_code, 400)

    def test_scan_success(self):
        token = generate_token(self.user.id, 10)

        response = self.client.post('/api/v1/checkins/scan/', {
            'token': token
        })

        self.assertEqual(response.status_code, 201)
        self.assertEqual(CheckIn.objects.count(), 1)

    def test_scan_duplicate(self):
        token = generate_token(self.user.id, 10)

        CheckIn.objects.create(employee_id=self.user.id, ngo_id=10)

        response = self.client.post('/api/v1/checkins/scan/', {
            'token': token
        })

        self.assertEqual(response.status_code, 400)

    # ─────────────────────────────
    # LIVE MONITOR
    # ─────────────────────────────
    def test_live_monitor_admin(self):
        self.client.force_authenticate(user=self.admin)

        CheckIn.objects.create(employee_id=1, ngo_id=10)

        response = self.client.get('/api/v1/checkins/live-monitor/10/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['checked_in_count'], 1)

    def test_live_monitor_non_admin_denied(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/v1/checkins/live-monitor/10/')

        self.assertEqual(response.status_code, 403)