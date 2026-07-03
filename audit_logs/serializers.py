from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer read-only untuk AuditLog."""

    user_name = serializers.SerializerMethodField()
    outlet_name = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            'id',
            'user',
            'user_name',
            'outlet',
            'outlet_name',
            'action',
            'object_type',
            'object_id',
            'changes',
            'notes',
            'created_at',
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        if obj.user:
            return str(obj.user)
        return None

    def get_outlet_name(self, obj):
        if obj.outlet:
            return obj.outlet.name
        return None