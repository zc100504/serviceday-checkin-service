from django.urls import path
from . import views

urlpatterns = [
    path('generate-qr/<int:ngo_id>/', views.generate_qr),          # GET  - admin gets QR
    path('employee-checkin/<int:ngo_id>/', views.employee_checkin), # POST - employee checks in
    path('live-monitor/<int:ngo_id>/', views.live_monitor),         # GET  - admin live view
]