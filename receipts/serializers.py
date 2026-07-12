"""Serializers untuk Receipt API."""
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from rest_framework.fields import CharField

from receipts.models import Receipt


class ReceiptListSerializer(serializers.ModelSerializer):
    """List receipt (ringan)."""

    session_id = serializers.IntegerField(source='session.id', read_only=True)
    customer_name = serializers.CharField(source='session.customer_name', read_only=True)
    printed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = [
            'id',
            'session_id',
            'customer_name',
            'invoice_number',
            'printed_by_name',
            'printed_at',
            'pdf_file',
        ]
        read_only_fields = fields

    @extend_schema_field(CharField())
    def get_printed_by_name(self, obj):
        return obj.printed_by.username


class ReceiptDetailSerializer(serializers.ModelSerializer):
    """Detail receipt."""

    session_id = serializers.IntegerField(source='session.id', read_only=True)
    customer_name = serializers.CharField(source='session.customer_name', read_only=True)
    total_amount = serializers.DecimalField(
        source='session.total_amount', max_digits=12, decimal_places=2, read_only=True,
    )
    outlet_name = serializers.CharField(source='session.outlet.name', read_only=True)
    printed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Receipt
        fields = [
            'id',
            'session_id',
            'customer_name',
            'total_amount',
            'outlet_name',
            'invoice_number',
            'pdf_file',
            'printed_by',
            'printed_by_name',
            'printed_at',
            'created_at',
        ]
        read_only_fields = fields

    @extend_schema_field(CharField())
    def get_printed_by_name(self, obj):
        return obj.printed_by.username


class GenerateReceiptSerializer(serializers.Serializer):
    """Request serializer untuk generate receipt."""

    session_id = serializers.IntegerField(required=True)