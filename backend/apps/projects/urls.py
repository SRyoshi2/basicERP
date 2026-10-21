from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AssigneeOptionView, ProjectViewSet, WorkPackageViewSet

router = DefaultRouter()
router.register("", ProjectViewSet, basename="project")

work_package_list = WorkPackageViewSet.as_view({"get": "list", "post": "create"})
work_package_detail = WorkPackageViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update"}
)
work_package_archive = WorkPackageViewSet.as_view({"post": "archive"})
work_package_history = WorkPackageViewSet.as_view({"get": "history"})

urlpatterns = [
    path("assignees/", AssigneeOptionView.as_view(), name="project-assignees"),
    path("work-packages/", work_package_list, name="work-package-list"),
    path("work-packages/<uuid:pk>/", work_package_detail, name="work-package-detail"),
    path("work-packages/<uuid:pk>/archive/", work_package_archive, name="work-package-archive"),
    path("work-packages/<uuid:pk>/history/", work_package_history, name="work-package-history"),
    *router.urls,
]
