"""ViewSet untuk Receipt API."""
from django.core.exceptions import ValidationError
from django.http import FileResponse
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from receipts.models import Receipt
from receipts.serializers import (
    ReceiptListSerializer,
    ReceiptDetailSerializer,
    GenerateReceiptSerializer,
)
from receipts.services import ReceiptService
from users.permissions import IsAdminOrOfficer


class ReceiptViewSet(viewsets.ModelViewSet):
    """ViewSet untuk Receipt — list, retrieve, create, download."""

    queryset = Receipt.objects.select_related(
        'session', 'session__outlet', 'printed_by',
    ).all()
    http_method_names = ['get', 'post', 'head', 'options']

    def get_permissions(self):
        if self.action in ['create', 'download']:
            self.permission_classes = [IsAdminOrOfficer]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'list':
            return ReceiptListSerializer
        if self.action == 'retrieve':
            return ReceiptDetailSerializer
        if self.action == 'create':
            return GenerateReceiptSerializer
        return ReceiptListSerializer

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
            receipt = ReceiptService.create_receipt(
                session_id=serializer.validated_data['session_id'],
                outlet_id=request.user.outlet_id,
                user_id=request.user.id,
            )
        except ValidationError as e:
            return Response(e.message_dict, status=status.HTTP_400_BAD_REQUEST)

        out_serializer = ReceiptDetailSerializer(receipt, context={'request': request})
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        """Download PDF receipt."""
        receipt = self.get_object()
        receipt.pdf_file.open('rb')
        response = FileResponse(
            receipt.pdf_file,
            content_type='application/pdf',
            filename=f'{receipt.invoice_number}.pdf',
        )
        return response