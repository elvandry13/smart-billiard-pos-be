from django.urls import path, include
from rest_framework.routers import DefaultRouter

from tables.views import (
    TableTypeViewSet,
    TableViewSet,
    PricingRuleViewSet,
    AdditionalFeeViewSet,
)

app_name = 'tables'

router = DefaultRouter()
router.register(r'table-types', TableTypeViewSet, basename='tabletype')
router.register(r'tables', TableViewSet, basename='table')
router.register(r'pricing-rules', PricingRuleViewSet, basename='pricingrule')
router.register(r'additional-fees', AdditionalFeeViewSet, basename='additionalfee')

urlpatterns = [
    path('', include(router.urls)),
]