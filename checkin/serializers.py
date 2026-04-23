from rest_framework import serializers
from .models import CheckIn


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = ['id', 'employee_id', 'ngo_id', 'checked_in_at']
        read_only_fields = ['id', 'checked_in_at']

    def validate_ngo_id(self, value):
        if value <= 0:
            raise serializers.ValidationError("Activity ID must be a positive number.")
        return value


class ScanTokenSerializer(serializers.Serializer):
    """Validates incoming scan requests"""
    token = serializers.CharField()

    def validate_token(self, value):
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("Token cannot be empty.")
        return value.strip()