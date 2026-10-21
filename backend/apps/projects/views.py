from django.db.models import Q
from django.contrib.auth import get_user_model
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasCompletedPasswordChange, IsAdministrator
from apps.core.serializers import ApiErrorResponseSerializer

from .models import Project, WorkPackage
from .serializers import (
    AssigneeOptionSerializer, ProjectAuditEventSerializer, ProjectControllingSerializer,
    ProjectCreateSerializer, ProjectSerializer, ProjectUpdateSerializer,
    WorkPackageAuditEventSerializer, WorkPackageCreateSerializer, WorkPackageSerializer,
    WorkPackageUpdateSerializer,
)
from .services import archive_project, archive_work_package, project_plan_controlling


class ProjectViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    queryset = Project.objects.select_related("customer")
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(parameters=[
        OpenApiParameter("search", OpenApiTypes.STR, description="Projektname, Projektnummer oder Kunde"),
        OpenApiParameter("status", OpenApiTypes.STR, enum=Project.Status.values),
        OpenApiParameter("customer", OpenApiTypes.UUID),
        OpenApiParameter("archived", OpenApiTypes.STR, enum=("false", "true", "all")),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(request=ProjectCreateSerializer, responses={201: ProjectSerializer, 400: ApiErrorResponseSerializer})
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(request=ProjectUpdateSerializer, responses={200: ProjectSerializer, 400: ApiErrorResponseSerializer, 409: ApiErrorResponseSerializer})
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def get_permissions(self):
        permissions = list(self.permission_classes)
        if self.action == "archive":
            permissions.append(IsAdministrator)
        return [permission() for permission in permissions]

    def get_serializer_class(self):
        if self.action == "create":
            return ProjectCreateSerializer
        if self.action in {"update", "partial_update"}:
            return ProjectUpdateSerializer
        return ProjectSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            archived = self.request.query_params.get("archived", "false").lower()
            if archived != "all":
                queryset = queryset.filter(archived_at__isnull=archived != "true")
            project_status = self.request.query_params.get("status")
            if project_status in Project.Status.values:
                queryset = queryset.filter(status=project_status)
            customer = self.request.query_params.get("customer")
            if customer:
                queryset = queryset.filter(customer_id=customer)
            query = self.request.query_params.get("search", "").strip()[:100]
            if query:
                queryset = queryset.filter(
                    Q(project_number__icontains=query) | Q(name__icontains=query)
                    | Q(customer__customer_number__icontains=query)
                    | Q(customer__company_name__icontains=query)
                    | Q(customer__first_name__icontains=query) | Q(customer__last_name__icontains=query)
                )
        return queryset

    @extend_schema(request=None, responses={200: ProjectSerializer})
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        return Response(ProjectSerializer(archive_project(self.get_object().pk, request.user)).data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: ProjectAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        return Response(ProjectAuditEventSerializer(self.get_object().audit_events.all(), many=True).data)

    @extend_schema(responses={200: ProjectControllingSerializer})
    @action(detail=True, methods=["get"], pagination_class=None)
    def controlling(self, request, pk=None):
        return Response(ProjectControllingSerializer(project_plan_controlling(self.get_object())).data)


class AssigneeOptionView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]

    @extend_schema(responses={200: AssigneeOptionSerializer(many=True)})
    def get(self, request):
        users = get_user_model().objects.filter(is_active=True).order_by("last_name", "first_name", "username")
        return Response(AssigneeOptionSerializer(users, many=True).data)


class WorkPackageViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = WorkPackage.objects.select_related("project", "assignee")
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(parameters=[
        OpenApiParameter("project", OpenApiTypes.UUID, required=True),
        OpenApiParameter("status", OpenApiTypes.STR, enum=WorkPackage.Status.values),
        OpenApiParameter("archived", OpenApiTypes.STR, enum=("false", "true", "all")),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=WorkPackageCreateSerializer,
        responses={201: WorkPackageSerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=WorkPackageUpdateSerializer,
        responses={200: WorkPackageSerializer, 400: ApiErrorResponseSerializer, 409: ApiErrorResponseSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def get_permissions(self):
        permissions = list(self.permission_classes)
        if self.action == "archive":
            permissions.append(IsAdministrator)
        return [permission() for permission in permissions]

    def get_serializer_class(self):
        if self.action == "create":
            return WorkPackageCreateSerializer
        if self.action in {"update", "partial_update"}:
            return WorkPackageUpdateSerializer
        return WorkPackageSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            project_id = self.request.query_params.get("project")
            if not project_id:
                return queryset.none()
            queryset = queryset.filter(project_id=project_id)
            package_status = self.request.query_params.get("status")
            if package_status in WorkPackage.Status.values:
                queryset = queryset.filter(status=package_status)
            archived = self.request.query_params.get("archived", "false").lower()
            if archived != "all":
                queryset = queryset.filter(archived_at__isnull=archived != "true")
        return queryset

    @extend_schema(request=None, responses={200: WorkPackageSerializer})
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        work_package = archive_work_package(self.get_object().pk, request.user)
        return Response(WorkPackageSerializer(work_package).data)

    @extend_schema(responses={200: WorkPackageAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        return Response(
            WorkPackageAuditEventSerializer(self.get_object().audit_events.all(), many=True).data
        )
