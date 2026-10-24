from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AbsenceRequestViewSet, LeaveBalanceView, LeaveEntitlementView

router = DefaultRouter()
router.register("absences", AbsenceRequestViewSet, basename="absence")

urlpatterns = [
    path("leave-balance/", LeaveBalanceView.as_view(), name="leave-balance"),
    path("leave-entitlements/", LeaveEntitlementView.as_view(), name="leave-entitlements"),
    *router.urls,
]
