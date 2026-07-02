from django.urls import path, include
from rest_framework.routers import DefaultRouter

from shifts.views import ShiftViewSet

app_name = 'shifts'

router = DefaultRouter()
router.register(r'shifts', ShiftViewSet, basename='shift')

urlpatterns = [
    path('', include(router.urls)),
]