from rest_framework import serializers

from payments.models import Payment


class PaymentListSerializer(serializers.ModelSerializer):
    """Serializer ringkas untuk list view."""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'session_id', 'method', 'status', 'amount',
            'paid_at', 'created_by_username',
        ]


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Serializer lengkap untuk detail view."""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    customer_name = serializers.CharField(source='session.customer_name', read_only=True)
    table_name = serializers.CharField(source='session.initial_table.name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id', 'session_id', 'method', 'status', 'amount',
            'gateway_reference', 'paid_at', 'created_at',
            'created_by', 'created_by_username',
            'customer_name', 'table_name',
        ]


class CreatePaymentSerializer(serializers.Serializer):
    """Serializer untuk input create payment."""
    session_id = serializers.IntegerField()
    method = serializers.ChoiceField(
        choices=Payment.Method.choices, default=Payment.Method.CASH,
    )
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    gateway_reference = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default='',
    )