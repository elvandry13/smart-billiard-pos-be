from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from rest_framework.fields import CharField

from tables.models import Table
from packages.models import Package
from shifts.models import Shift
from users.models import User

from .models import PlaySession, SessionTableLog


# ---------------------------------------------------------------------------
# SessionTableLog Serializers
# ---------------------------------------------------------------------------
class SessionTableLogSerializer(serializers.ModelSerializer):
    """Serializer read-only untuk SessionTableLog."""

    table_name = serializers.SerializerMethodField()

    class Meta:
        model = SessionTableLog
        fields = [
            'id',
            'session',
            'table',
            'table_name',
            'rate_source_type',
            'rate_source_snapshot',
            'started_at',
            'ended_at',
            'duration_minutes',
            'amount',
        ]
        read_only_fields = fields

    @extend_schema_field(CharField(allow_null=True))
    def get_table_name(self, obj):
        return obj.table.name if obj.table else None


class SessionTableLogNestedSerializer(serializers.ModelSerializer):
    """Nested read-only serializer untuk table logs di dalam PlaySession."""

    table_name = serializers.SerializerMethodField()

    class Meta:
        model = SessionTableLog
        fields = [
            'id',
            'table',
            'table_name',
            'rate_source_type',
            'rate_source_snapshot',
            'started_at',
            'ended_at',
            'duration_minutes',
            'amount',
        ]
        read_only_fields = fields

    @extend_schema_field(CharField(allow_null=True))
    def get_table_name(self, obj):
        return obj.table.name if obj.table else None


# ---------------------------------------------------------------------------
# PlaySession Serializers
# ---------------------------------------------------------------------------
class PlaySessionListSerializer(serializers.ModelSerializer):
    """Serializer untuk list sessions (ringan)."""

    outlet_name = serializers.SerializerMethodField()
    officer_start_name = serializers.SerializerMethodField()
    initial_table_name = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()
    active_table_name = serializers.SerializerMethodField()

    class Meta:
        model = PlaySession
        fields = [
            'id',
            'outlet',
            'outlet_name',
            'shift',
            'customer_name',
            'customer_phone',
            'initial_table',
            'initial_table_name',
            'package',
            'package_name',
            'status',
            'started_at',
            'active_table_name',
            'officer_start',
            'officer_start_name',
        ]
        read_only_fields = fields

    @extend_schema_field(CharField(allow_null=True))
    def get_outlet_name(self, obj):
        return obj.outlet.name if obj.outlet else None

    @extend_schema_field(CharField(allow_null=True))
    def get_officer_start_name(self, obj):
        return obj.officer_start.username if obj.officer_start else None

    @extend_schema_field(CharField(allow_null=True))
    def get_initial_table_name(self, obj):
        return obj.initial_table.name if obj.initial_table else None

    @extend_schema_field(CharField(allow_null=True))
    def get_package_name(self, obj):
        return obj.package.name if obj.package else None

    @extend_schema_field(CharField(allow_null=True))
    def get_active_table_name(self, obj):
        for log in obj.table_logs.all():
            if log.ended_at is None:
                return log.table.name if log.table else None
        return None


class PlaySessionDetailSerializer(serializers.ModelSerializer):
    """Serializer detail PlaySession dengan nested table_logs."""

    outlet_name = serializers.SerializerMethodField()
    officer_start_name = serializers.SerializerMethodField()
    officer_end_name = serializers.SerializerMethodField()
    initial_table_name = serializers.SerializerMethodField()
    package_name = serializers.SerializerMethodField()
    shift_officer_name = serializers.SerializerMethodField()
    table_logs = SessionTableLogNestedSerializer(many=True, read_only=True)

    class Meta:
        model = PlaySession
        fields = [
            'id',
            'outlet',
            'outlet_name',
            'shift',
            'shift_officer_name',
            'customer_name',
            'customer_phone',
            'initial_table',
            'initial_table_name',
            'package',
            'package_name',
            'status',
            'started_at',
            'ended_at',
            'officer_start',
            'officer_start_name',
            'officer_end',
            'officer_end_name',
            'subtotal',
            'additional_fee_total',
            'total_amount',
            'cancel_reason',
            'created_at',
            'table_logs',
        ]
        read_only_fields = fields

    @extend_schema_field(CharField(allow_null=True))
    def get_outlet_name(self, obj):
        return obj.outlet.name if obj.outlet else None

    @extend_schema_field(CharField(allow_null=True))
    def get_officer_start_name(self, obj):
        return obj.officer_start.username if obj.officer_start else None

    @extend_schema_field(CharField(allow_null=True))
    def get_officer_end_name(self, obj):
        return obj.officer_end.username if obj.officer_end else None

    @extend_schema_field(CharField(allow_null=True))
    def get_initial_table_name(self, obj):
        return obj.initial_table.name if obj.initial_table else None

    @extend_schema_field(CharField(allow_null=True))
    def get_package_name(self, obj):
        return obj.package.name if obj.package else None

    @extend_schema_field(CharField(allow_null=True))
    def get_shift_officer_name(self, obj):
        return obj.shift.officer.username if obj.shift and obj.shift.officer else None


# ---------------------------------------------------------------------------
# Request Serializers (write operations)
# ---------------------------------------------------------------------------
class OpenSessionRequestSerializer(serializers.Serializer):
    outlet_id = serializers.IntegerField(required=False)
    shift_id = serializers.IntegerField()
    customer_name = serializers.CharField(max_length=100)
    customer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    initial_table_id = serializers.IntegerField()
    package_id = serializers.IntegerField(required=False, allow_null=True)


class TransferTableRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    new_table_id = serializers.IntegerField()


class EndSessionRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()


class CancelSessionRequestSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    cancel_reason = serializers.CharField(max_length=500)