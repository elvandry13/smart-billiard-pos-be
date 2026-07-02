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
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserProfileSerializer(user).data,
        })


class LogoutView(generics.GenericAPIView):
    """Logout endpoint — blacklist refresh token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
            except Exception:
                # Token invalid/expired — silently ignore, can't blacklist
                pass
            else:
                token.blacklist()  # failures propagate
        return Response({'detail': 'Logout berhasil.'})


class ProfileView(generics.RetrieveUpdateAPIView):
    """View & edit profile user yang sedang login."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user


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
        return Response({'detail': 'Password berhasil diubah.'})


class TenantViewSet(viewsets.ModelViewSet):
    """CRUD Tenant — hanya Super Admin."""
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    filterset_fields = ['is_active']
    search_fields = ['name', 'code']


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
        serializer.save(**extra)

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
        serializer.save()
