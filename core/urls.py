"""URL configuration for core project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from core.views import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    # Health check
    path('api/health/', health_check, name='health-check'),
    # API
    path('api/', include('users.urls')),
    path('api/', include('tables.urls')),
    path('api/', include('packages.urls')),
    path('api/', include('shifts.urls')),
    path('api/', include('sessions.urls')),
    path('api/', include('payments.urls')),
    path('api/', include('receipts.urls')),
    path('api/', include('audit_logs.urls')),
    path('api/', include('dashboard.urls')),
    # API Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development (PDF receipts)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)