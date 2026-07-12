from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from rest_framework.fields import CharField

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

    @extend_schema_field(CharField(allow_null=True))
    def get_user_name(self, obj):
        if obj.user:
            return str(obj.user)
        return None

    @extend_schema_field(CharField(allow_null=True))
    def get_outlet_name(self, obj):
        if obj.outlet:
            return obj.outlet.name
        return None