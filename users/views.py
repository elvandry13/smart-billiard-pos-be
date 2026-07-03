from django.db import transaction
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, Tenant, Outlet
from .serializers import (
    LoginSerializer,
    UserProfileSerializer,
    UserCreateSerializer,
    UserListSerializer,
    TenantSerializer,
    OutletSerializer,
    ChangePasswordSerializer,
)
from .permissions import IsSuperAdmin, IsAdminOrSuperAdminOrOwner, IsAdminOrSuperAdmin
from audit_logs.services import AuditService


class LoginView(generics.GenericAPIView):
    """Login endpoint — mengembalikan JWT access + refresh token."""
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data['username']
        password = serializer.validated_data['password']
        user = authenticate(username=username, password=password)

        if user is None:
            return Response(
                {'detail': 'Username atau password tidak valid.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {'detail': 'Akun tidak aktif.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        AuditService.log(
            user_id=user.id,
            outlet_id=getattr(user, 'outlet_id', None),
            action='login',
            object_type='User',
            object_id=user.id,
        )
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data,
        })


class LogoutView(generics.GenericAPIView):
    """Logout endpoint — blacklist refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
            except Exception:
                # Token invalid/expired — silently ignore, can't blacklist
                pass
            else:
                token.blacklist()  # failures propagate
        AuditService.log(
            user_id=user.id,
            outlet_id=getattr(user, 'outlet_id', None),
            action='logout',
            object_type='User',
            object_id=user.id,
        )
        return Response({'detail': 'Logout berhasil.'})


class ProfileView(generics.RetrieveUpdateAPIView):
    """View & edit profile user yang sedang login."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user

    def perform_update(self, serializer):
        user = serializer.save()
        AuditService.log(
            user_id=user.id,
            outlet_id=getattr(user, 'outlet_id', None),
            action='update_profile',
            object_type='User',
            object_id=user.id,
        )


class ChangePasswordView(generics.GenericAPIView):
    """Ganti password user yang sedang login."""
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer

    def post(self, request, *args, **kwargs):
        return self._handle_change(request)

    def put(self, request, *args, **kwargs):
        return self._handle_change(request)

    def _handle_change(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        AuditService.log(
            user_id=user.id,
            outlet_id=getattr(user, 'outlet_id', None),
            action='change_password',
            object_type='User',
            object_id=user.id,
        )
        return Response({'detail': 'Password berhasil diubah.'})


class TenantViewSet(viewsets.ModelViewSet):
    """CRUD Tenant — hanya Super Admin."""
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']

    def perform_create(self, serializer):
        tenant = serializer.save()
        AuditService.log(
            user_id=self.request.user.id,
            outlet_id=None,
            action='create_tenant',
            object_type='Tenant',
            object_id=tenant.id,
        )

    def perform_update(self, serializer):
        tenant = serializer.save()
        AuditService.log(
            user_id=self.request.user.id,
            outlet_id=None,
            action='update_tenant',
            object_type='Tenant',
            object_id=tenant.id,
        )

    def perform_destroy(self, instance):
        tenant_id = instance.id
        with transaction.atomic():
            instance.delete()
            AuditService.log(
                user_id=self.request.user.id,
                outlet_id=None,
                action='delete_tenant',
                object_type='Tenant',
                object_id=tenant_id,
            )


class OutletViewSet(viewsets.ModelViewSet):
    """CRUD Outlet — hanya Super Admin."""
    queryset = Outlet.objects.select_related('tenant').all()
    serializer_class = OutletSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    filterset_fields = ['tenant', 'is_active']
    search_fields = ['name', 'code']

    def get_queryset(self):
        qs = super().get_queryset()
        tenant_id = self.request.query_params.get('tenant')
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        return qs

    def perform_create(self, serializer):
        outlet = serializer.save()
        AuditService.log(
            user_id=self.request.user.id,
            outlet_id=outlet.id,
            action='create_outlet',
            object_type='Outlet',
            object_id=outlet.id,
        )

    def perform_update(self, serializer):
        outlet = serializer.save()
        AuditService.log(
            user_id=self.request.user.id,
            outlet_id=outlet.id,
            action='update_outlet',
            object_type='Outlet',
            object_id=outlet.id,
        )

    def perform_destroy(self, instance):
        outlet_id = instance.id
        with transaction.atomic():
            instance.delete()
            AuditService.log(
                user_id=self.request.user.id,
                outlet_id=outlet_id,
                action='delete_outlet',
                object_type='Outlet',
                object_id=outlet_id,
            )


class UserViewSet(viewsets.ModelViewSet):
    """
    CRUD User.
    - Super Admin: lihat & kelola semua user.
    - Admin: lihat & kelola user di outlet-nya saja (Admin + Officer).
    - Owner: read-only user di tenant-nya.
    """
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            # Super Admin, Owner, Admin bisa lihat
            return [IsAuthenticated(), IsAdminOrSuperAdminOrOwner()]
        return [IsAuthenticated(), IsAdminOrSuperAdmin()]

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        if self.action in ['list', 'retrieve']:
            return UserListSerializer
        return UserCreateSerializer  # update pakai serializer yang sama

    def get_queryset(self):
        user = self.request.user
        if user.is_super_admin:
            return User.objects.all()
        if user.is_owner:
            # Owner bisa lihat user di tenant-nya
            return User.objects.filter(tenant=user.tenant)
        if user.is_admin:
            # Admin hanya lihat user di outlet-nya
            return User.objects.filter(outlet=user.outlet)
        return User.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        role = serializer.validated_data.get('role', '')
        # Admin tidak boleh membuat Super Admin atau Owner
        if user.is_admin and role in [User.RoleEnum.SUPER_ADMIN, User.RoleEnum.OWNER]:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Admin tidak dapat membuat user dengan role Super Admin atau Owner.')
        extra = {}
        if user.is_admin:
            extra['outlet'] = user.outlet
            extra['tenant'] = user.tenant
        new_user = serializer.save(**extra)
        AuditService.log(
            user_id=user.id,
            outlet_id=getattr(new_user, 'outlet_id', None),
            action='create_user',
            object_type='User',
            object_id=new_user.id,
        )

    def perform_update(self, serializer):
        user = self.request.user
        role = serializer.validated_data.get('role', '')
        # Admin tidak boleh mengubah role menjadi Super Admin atau Owner
        if user.is_admin and role in [User.RoleEnum.SUPER_ADMIN, User.RoleEnum.OWNER]:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('Admin tidak dapat mengubah role user menjadi Super Admin atau Owner.')
        # Admin tidak boleh memindahkan user ke tenant/outlet lain
        if user.is_admin:
            serializer.validated_data['tenant'] = user.tenant
            serializer.validated_data['outlet'] = user.outlet
        updated_user = serializer.save()
        AuditService.log(
            user_id=user.id,
            outlet_id=getattr(updated_user, 'outlet_id', None),
            action='update_user',
            object_type='User',
            object_id=updated_user.id,
        )

    def perform_destroy(self, instance):
        user_id = instance.id
        outlet_id = getattr(instance, 'outlet_id', None)
        with transaction.atomic():
            instance.delete()
            AuditService.log(
                user_id=self.request.user.id,
                outlet_id=outlet_id,
                action='delete_user',
                object_type='User',
                object_id=user_id,
            )
