import qrcode
import base64
from io import BytesIO

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .models import CheckIn


# ─────────────────────────────────────────────────────
# GET /api/v1/checkin/generate-qr/<ngo_id>/
# Admin generates QR code for an NGO activity
# ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAdminUser])
def generate_qr(request, ngo_id):
    
    # ← Point to GATEWAY, not this service
    # Gateway handles session/cookie auth, not JWT
    gateway_url = f"http://localhost:8000/checkin/employee/{ngo_id}/"

    qr = qrcode.QRCode(box_size=10, border=2)
    qr.add_data(gateway_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return Response({
        'ngo_id': ngo_id,
        'checkin_url': gateway_url,
        'qr_code_base64': qr_base64,
    })

# ─────────────────────────────────────────────────────
# POST /api/v1/checkin/employee-checkin/<ngo_id>/
# Employee scans QR → this endpoint records the checkin
# ─────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def employee_checkin(request, ngo_id):
    employee_id = request.user.id

    # Already checked in?
    if CheckIn.objects.filter(employee_id=employee_id, ngo_id=ngo_id).exists():
        return Response(
            {'error': 'You have already checked in for this activity.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    checkin = CheckIn.objects.create(
        employee_id=employee_id,
        ngo_id=ngo_id,
    )

    return Response({
        'message': 'Check-in successful!',
        'checked_in_at': checkin.checked_in_at,
    }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────
# GET /api/v1/checkin/live-monitor/<ngo_id>/
# Admin views live checkin list for an NGO
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

    checked_in_count = records.count()

    return Response({
        'ngo_id': ngo_id,
        'checked_in_count': checked_in_count,
        'checkins': checkins,
    })