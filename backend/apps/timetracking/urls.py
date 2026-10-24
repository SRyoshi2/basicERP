from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ProjectTimeSummaryView, ServiceEntryViewSet, TimeEntryViewSet

router = DefaultRouter()
router.register("entries", TimeEntryViewSet, basename="time-entry")
router.register("service-entries", ServiceEntryViewSet, basename="service-entry")

urlpatterns = [
    path("project-summary/", ProjectTimeSummaryView.as_view(), name="project-time-summary"),
    *router.urls,
]
