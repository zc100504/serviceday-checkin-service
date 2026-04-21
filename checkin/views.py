import qrcode
import base64
import jwt
import datetime
from io import BytesIO

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.response import Response
from rest_framework import status

from .models import CheckIn


def generate_token(employee_id, ngo_id):
    """Create a unique signed token per employee per activity"""
    payload = {
        'employee_id': employee_id,
        'ngo_id': ngo_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),  # expires in 24hrs
        'iat': datetime.datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token


def decode_token(token):
    """Verify and decode the token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, 'QR code has expired.'
    except jwt.InvalidTokenError:
        return None, 'Invalid QR code.'


# ─────────────────────────────────────────────────────
# GET /api/v1/checkins/generate-qr/<ngo_id>/
# Each EMPLOYEE generates their own unique QR
# ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def generate_qr(request, ngo_id):
    employee_id = request.user.id

    # Already checked in? No need for QR
    if CheckIn.objects.filter(employee_id=employee_id, ngo_id=ngo_id).exists():
        return Response(
            {'error': 'You have already checked in for this activity.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Generate unique token for THIS employee + THIS activity
    token = generate_token(employee_id, ngo_id)

    # QR encodes the scan URL with unique token
    scan_url = f"http://localhost:8000/checkin/scan/?token={token}"

    # Build QR image
    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return Response({
        'employee_id': employee_id,
        'ngo_id': ngo_id,
        'token': token,
        'scan_url': scan_url,
        'qr_code_base64': qr_base64,   # frontend renders this
    })


# ─────────────────────────────────────────────────────
# POST /api/v1/checkins/scan/
# Called when QR is scanned — verifies token & records checkin
# ─────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([AllowAny])   # no JWT needed — token IS the auth
def scan_checkin(request):
    token = request.data.get('token')

    if not token:
        return Response(
            {'error': 'Token is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Verify token
    payload, error = decode_token(token)
    if error:
        return Response(
            {'error': error},
            status=status.HTTP_400_BAD_REQUEST
        )

    employee_id = payload['employee_id']
    ngo_id = payload['ngo_id']

    # Already checked in?
    if CheckIn.objects.filter(employee_id=employee_id, ngo_id=ngo_id).exists():
        return Response(
            {'error': 'Already checked in.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Record checkin
    checkin = CheckIn.objects.create(
        employee_id=employee_id,
        ngo_id=ngo_id,
    )

    return Response({
        'message': 'Check-in successful!',
        'employee_id': employee_id,
        'ngo_id': ngo_id,
        'checked_in_at': checkin.checked_in_at,
    }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────
# GET /api/v1/checkins/live-monitor/<ngo_id>/
# Admin views who checked in
# ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAdminUser])
def live_monitor(request, ngo_id):
    records = CheckIn.objects.filter(ngo_id=ngo_id).order_by('-checked_in_at')

    checkins = [
        {
            'employee_id': r.employee_id,
            'checked_in_at': r.checked_in_at,
        }
        for r in records
    ]

    return Response({
        'ngo_id': ngo_id,
        'checked_in_count': records.count(),
        'checkins': checkins,
    })