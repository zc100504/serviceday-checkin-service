from rest_framework import serializers
from .models import CheckIn


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = ['id', 'employee_id', 'ngo_id', 'checked_in_at']
        read_only_fields = ['id', 'checked_in_at']