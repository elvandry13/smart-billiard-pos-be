from django.urls import path, include
from rest_framework.routers import DefaultRouter

from receipts.views import ReceiptViewSet

router = DefaultRouter()
router.register(r'receipts', ReceiptViewSet, basename='receipt')

urlpatterns = [
    path('', include(router.urls)),
]