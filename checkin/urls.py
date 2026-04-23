from django.urls import path
from . import views

urlpatterns = [
    path('generate-qr/<int:ngo_id>/', views.generate_qr),  # GET  - admin generates
    path('scan/', views.scan_checkin),                      # POST - employee scans
    path('live-monitor/<int:ngo_id>/', views.live_monitor), # GET  - admin views list
]