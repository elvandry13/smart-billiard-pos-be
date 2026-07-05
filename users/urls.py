from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LoginView,
    LogoutView,
    ProfileView,
    ChangePasswordView,
    TenantViewSet,
    OutletViewSet,
    UserViewSet,
    ThrottledTokenRefreshView,
)

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)
router.register(r'outlets', OutletViewSet)
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    # Auth
    path('auth/login/', LoginView.as_view(), name='auth-login'),
    path('auth/logout/', LogoutView.as_view(), name='auth-logout'),
    path('auth/refresh/', ThrottledTokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/password/change/', ChangePasswordView.as_view(), name='auth-password-change'),
    # Profile
    path('profile/', ProfileView.as_view(), name='profile'),
    # CRUD (via ViewSet router)
    path('', include(router.urls)),
]