from django.urls import path, include
from rest_framework.routers import DefaultRouter

from packages.views import PackageViewSet

app_name = 'packages'

router = DefaultRouter()
router.register(r'packages', PackageViewSet, basename='package')

urlpatterns = [
    path('', include(router.urls)),
]