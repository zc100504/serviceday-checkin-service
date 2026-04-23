import qrcode
import base64
import jwt
import datetime
from io import BytesIO

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from .permissions import IsEmployee, IsAdministrator, IsEmployeeOrAdmin
from rest_framework.response import Response
from rest_framework import status

from .models import CheckIn
from .serializers import CheckInSerializer, ScanRequestSerializer

def generate_token(employee_id, ngo_id):
    payload = {
        'employee_id': employee_id,
        'ngo_id': ngo_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        'iat': datetime.datetime.utcnow(),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
    return token


def decode_token(token):
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
@permission_classes([IsAdministrator])
def generate_qr(request, ngo_id):

    # QR encodes the scan URL with ngo_id only — no employee_id
    scan_url = f"http://localhost:8000/checkin/scan/?ngo_id={ngo_id}"

    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return Response({
        'ngo_id': ngo_id,
        'scan_url': scan_url,
        'qr_code_base64': qr_base64,
    })

# ─────────────────────────────────────────────────────
# POST /api/v1/checkins/scan/
# Called when QR is scanned — verifies token & records checkin
# ─────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsEmployee])   # ← employee must be logged in
def scan_checkin(request):

    serializer = ScanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    ngo_id = request.data.get('ngo_id')
    employee_id = request.user.get('user_id')   # ← from their JWT

    if not ngo_id:
        return Response(
            {'error': 'ngo_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if CheckIn.objects.filter(employee_id=employee_id, ngo_id=ngo_id).exists():
        return Response(
            {'error': 'Already checked in.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    checkin = CheckIn.objects.create(
        employee_id=employee_id,
        ngo_id=ngo_id,
    )

    return Response({
        'message': 'Check-in successful!',
        'checkin': CheckInSerializer(checkin).data
    }, status=status.HTTP_201_CREATED)

# ─────────────────────────────────────────────────────
# GET /api/v1/checkins/live-monitor/<ngo_id>/
# Admin views who checked in
# ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAdministrator])
def live_monitor(request, ngo_id):
    records = CheckIn.objects.filter(ngo_id=ngo_id).order_by('-checked_in_at')
    serializer = CheckInSerializer(records, many=True)    # ← serializer

    return Response({
        'ngo_id': ngo_id,
        'checked_in_count': records.count(),
        'checkins': serializer.data
    })