from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ProjectTimeSummaryView, TimeEntryViewSet

router = DefaultRouter()
router.register("entries", TimeEntryViewSet, basename="time-entry")

urlpatterns = [
    path("project-summary/", ProjectTimeSummaryView.as_view(), name="project-time-summary"),
    *router.urls,
]
