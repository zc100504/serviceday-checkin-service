from django.urls import path
from . import views

urlpatterns = [
    path('generate-qr/<int:ngo_id>/', views.generate_qr),  # GET  - employee gets their QR
    path('scan/', views.scan_checkin),                      # POST - scan verifies token
    path('live-monitor/<int:ngo_id>/', views.live_monitor), # GET  - admin live view
]