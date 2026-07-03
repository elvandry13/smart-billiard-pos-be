from django.core.exceptions import ValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import PlaySession, SessionTableLog
from .serializers import (
    PlaySessionListSerializer,
    PlaySessionDetailSerializer,
    SessionTableLogSerializer,
    OpenSessionRequestSerializer,
    TransferTableRequestSerializer,
    EndSessionRequestSerializer,
    CancelSessionRequestSerializer,
)
from .services import SessionService
from users.permissions import IsOfficerOrSuperAdmin


class PlaySessionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet untuk PlaySession.

    - list/retrieve: semua authenticated user (dengan filtering by role)
    - create/update/delete: officer/super_admin only untuk write
    - custom actions: open, transfer_table, end_session, cancel_session, table_logs, table_log_detail
    """

    queryset = PlaySession.objects.select_related(
        'outlet', 'shift', 'initial_table', 'package',
        'officer_start', 'officer_end',
    ).prefetch_related('table_logs__table').all()

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'outlet', 'shift', 'package']
    search_fields = ['customer_name', 'customer_phone']
    ordering_fields = ['started_at', 'ended_at', 'total_amount']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsOfficerOrSuperAdmin()]

    def get_serializer_class(self):
        if self.action == 'list':
            return PlaySessionListSerializer
        elif self.action == 'retrieve':
            return PlaySessionDetailSerializer
        elif self.action in ('open', 'transfer_table', 'end_session', 'cancel_session'):
            return None  # Custom serializers per action
        return PlaySessionDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_super_admin:
            return qs

        if user.is_admin:
            return qs.filter(outlet=user.outlet)

        if user.is_officer:
            return qs.filter(outlet=user.outlet)

        return qs.none()

    # ------------------------------------------------------------------
    # Custom Actions
    # ------------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='open')
    def open(self, request):
        """POST /api/sessions/open/ — Buka sesi bermain baru."""
        serializer = OpenSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        user = request.user

        # Non-super-admin: auto-inject outlet & officer
        if not user.is_super_admin:
            data['outlet_id'] = user.outlet_id
            data['officer_start_id'] = user.id
        else:
            data['officer_start_id'] = request.data.get('officer_start_id', user.id)

        try:
            session = SessionService.open_session(
                outlet_id=data['outlet_id'],
                shift_id=data['shift_id'],
                customer_name=data['customer_name'],
                customer_phone=data.get('customer_phone', ''),
                initial_table_id=data['initial_table_id'],
                officer_start_id=data['officer_start_id'],
                package_id=data.get('package_id'),
            )
        except ValidationError as e:
            return Response(e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        # Refresh with prefetched
        session = self.get_queryset().get(pk=session.pk)
        serializer_out = PlaySessionDetailSerializer(session)
        return Response(serializer_out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='transfer-table')
    def transfer_table(self, request):
        """POST /api/sessions/transfer-table/ — Pindah meja."""
        serializer = TransferTableRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            new_log = SessionService.transfer_table(
                session_id=data['session_id'],
                new_table_id=data['new_table_id'],
                officer_id=request.user.id,
            )
        except ValidationError as e:
            return Response(e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer_out = SessionTableLogSerializer(new_log)
        return Response(serializer_out.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='end-session')
    def end_session(self, request):
        """POST /api/sessions/end-session/ — Akhiri sesi bermain."""
        serializer = EndSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            session = SessionService.end_session(
                session_id=data['session_id'],
                officer_end_id=request.user.id,
            )
        except ValidationError as e:
            return Response(e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        session = self.get_queryset().get(pk=session.pk)
        serializer_out = PlaySessionDetailSerializer(session)
        return Response(serializer_out.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='cancel-session')
    def cancel_session(self, request):
        """POST /api/sessions/cancel-session/ — Batalkan sesi bermain."""
        serializer = CancelSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        try:
            session = SessionService.cancel_session(
                session_id=data['session_id'],
                officer_end_id=request.user.id,
                cancel_reason=data['cancel_reason'],
            )
        except ValidationError as e:
            return Response(e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        session = self.get_queryset().get(pk=session.pk)
        serializer_out = PlaySessionDetailSerializer(session)
        return Response(serializer_out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='table-logs')
    def table_logs(self, request, pk=None):
        """GET /api/sessions/{id}/table-logs/ — List semua table logs untuk satu sesi."""
        logs = SessionTableLog.objects.filter(
            session_id=pk,
        ).select_related('table').order_by('started_at')

        serializer = SessionTableLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='table-logs/(?P<log_pk>[^/.]+)')
    def table_log_detail(self, request, pk=None, log_pk=None):
        """GET /api/sessions/{id}/table-logs/{log_pk}/ — Detail satu table log."""
        log = SessionTableLog.objects.filter(
            session_id=pk,
            pk=log_pk,
        ).select_related('table').first()

        if not log:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SessionTableLogSerializer(log)
        return Response(serializer.data)