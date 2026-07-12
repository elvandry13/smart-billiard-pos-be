from django.core.exceptions import ValidationError
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

from .models import PlaySession
from .filters import SessionFilter
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
from audit_logs.services import AuditService
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
    filterset_class = SessionFilter
    search_fields = ['customer_name', 'customer_phone']
    ordering_fields = ['started_at', 'ended_at', 'total_amount']

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [IsAuthenticated()]
        return [IsOfficerOrSuperAdmin()]

    def get_serializer_class(self):
        if getattr(self, 'swagger_fake_view', False):
            return PlaySessionDetailSerializer
        if self.action == 'list':
            return PlaySessionListSerializer
        elif self.action == 'retrieve':
            return PlaySessionDetailSerializer
        elif self.action in ('open', 'transfer_table', 'end_session', 'cancel_session'):
            return None  # Custom serializers per action
        return PlaySessionDetailSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if getattr(self, 'swagger_fake_view', False):
            return qs
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
            if 'outlet_id' not in data:
                return Response(
                    {'outlet_id': 'This field is required.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

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
        AuditService.log(
            user_id=request.user.id,
            outlet_id=session.outlet_id,
            action='open_session',
            object_type='PlaySession',
            object_id=session.id,
        )
        serializer_out = PlaySessionDetailSerializer(session)
        return Response(serializer_out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='transfer-table')
    def transfer_table(self, request):
        """POST /api/sessions/transfer-table/ — Pindah meja."""
        serializer = TransferTableRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Verify session belongs to user's outlet
        try:
            self.get_queryset().get(pk=data['session_id'])
        except PlaySession.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            new_log = SessionService.transfer_table(
                session_id=data['session_id'],
                new_table_id=data['new_table_id'],
                officer_id=request.user.id,
            )
        except ValidationError as e:
            return Response(e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        AuditService.log(
            user_id=request.user.id,
            outlet_id=new_log.session.outlet_id,
            action='transfer_table',
            object_type='PlaySession',
            object_id=data['session_id'],
            changes={'new_table_id': new_log.table_id},
        )
        serializer_out = SessionTableLogSerializer(new_log)
        return Response(serializer_out.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='end-session')
    def end_session(self, request):
        """POST /api/sessions/end-session/ — Akhiri sesi bermain."""
        serializer = EndSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Verify session belongs to user's outlet
        try:
            self.get_queryset().get(pk=data['session_id'])
        except PlaySession.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            session = SessionService.end_session(
                session_id=data['session_id'],
                officer_end_id=request.user.id,
            )
        except ValidationError as e:
            return Response(e.message_dict if hasattr(e, 'message_dict') else {'detail': str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        session = self.get_queryset().get(pk=session.pk)
        AuditService.log(
            user_id=request.user.id,
            outlet_id=session.outlet_id,
            action='end_session',
            object_type='PlaySession',
            object_id=session.id,
            changes={'total_amount': str(session.total_amount) if session.total_amount is not None else None},
        )
        serializer_out = PlaySessionDetailSerializer(session)
        return Response(serializer_out.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='cancel-session')
    def cancel_session(self, request):
        """POST /api/sessions/cancel-session/ — Batalkan sesi bermain."""
        serializer = CancelSessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Verify session belongs to user's outlet
        try:
            self.get_queryset().get(pk=data['session_id'])
        except PlaySession.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

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
        AuditService.log(
            user_id=request.user.id,
            outlet_id=session.outlet_id,
            action='cancel_session',
            object_type='PlaySession',
            object_id=session.id,
            notes=data['cancel_reason'],
        )
        serializer_out = PlaySessionDetailSerializer(session)
        return Response(serializer_out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='table-logs')
    def table_logs(self, request, pk=None):
        """GET /api/sessions/{id}/table-logs/ — List semua table logs untuk satu sesi."""
        # Resolve session through scoped queryset first
        session = self.get_object()
        logs = session.table_logs.select_related('table').order_by('started_at')

        serializer = SessionTableLogSerializer(logs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='table-logs/(?P<log_pk>[^/.])')
    def table_log_detail(self, request, pk=None, log_pk=None):
        """GET /api/sessions/{id}/table-logs/{log_pk}/ — Detail satu table log."""
        # Resolve session through scoped queryset first
        session = self.get_object()
        log = session.table_logs.filter(pk=log_pk).select_related('table').first()

        if not log:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = SessionTableLogSerializer(log)
        return Response(serializer.data)
