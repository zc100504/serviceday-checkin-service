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


class ScanRequestSerializer(serializers.Serializer):
    """Validates incoming scan requests"""
    ngo_id = serializers.IntegerField()

    def validate_ngo_id(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Activity ID must be a positive number."
            )
        return value