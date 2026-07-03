from django.core.exceptions import ValidationError
from rest_framework import viewsets, status
from rest_framework.response import Response

from payments.models import Payment
from payments.serializers import (
    PaymentListSerializer,
    PaymentDetailSerializer,
    CreatePaymentSerializer,
)
from payments.services import PaymentService
from users.permissions import IsAdminOrOfficer


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet untuk Payment — read-only untuk list/retrieve, create untuk cash payment."""
    queryset = Payment.objects.select_related('session', 'created_by').all()
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in ['create']:
            self.permission_classes = [IsAdminOrOfficer]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'list':
            return PaymentListSerializer
        if self.action == 'retrieve':
            return PaymentDetailSerializer
        if self.action == 'create':
            return CreatePaymentSerializer
        return PaymentListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_super_admin:
            return qs
        return qs.filter(session__outlet=user.outlet)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = PaymentService.create_payment(
                session_id=serializer.validated_data['session_id'],
                method=serializer.validated_data.get(
                    'method', Payment.Method.CASH,
                ),
                amount=serializer.validated_data['amount'],
                created_by_id=request.user.id,
                gateway_reference=serializer.validated_data.get('gateway_reference', ''),
            )
        except ValidationError as e:
            return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = PaymentDetailSerializer(payment, context={'request': request})
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)