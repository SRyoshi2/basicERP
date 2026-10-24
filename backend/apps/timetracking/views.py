import csv
from io import StringIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.models import User
from apps.core.permissions import HasCompletedPasswordChange
from apps.core.serializers import ApiErrorResponseSerializer
from apps.projects.models import Project

from .models import ServiceEntry, TimeEntry
from .reporting import build_time_report
from .serializers import (
    ProjectTimeSummarySerializer, ServiceEntryAuditEventSerializer, ServiceEntryCreateSerializer,
    ServiceEntrySerializer, ServiceEntryUpdateSerializer, TimeEntryAuditEventSerializer,
    TimeEntryCreateSerializer, TimeEntrySerializer, TimeEntryUpdateSerializer,
    TimeReportFilterSerializer, TimeReportSerializer,
)
from .services import archive_service_entry, archive_time_entry, project_time_summary


class TimeEntryPagination(PageNumberPagination):
    page_size = 100
    max_page_size = 200


class TimeEntryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = TimeEntry.objects.select_related("employee", "project", "work_package")
    pagination_class = TimeEntryPagination
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(parameters=[
        OpenApiParameter("date_from", OpenApiTypes.DATE),
        OpenApiParameter("date_to", OpenApiTypes.DATE),
        OpenApiParameter("project", OpenApiTypes.UUID),
        OpenApiParameter("employee", OpenApiTypes.INT, description="Nur für Administratoren"),
        OpenApiParameter("billable", OpenApiTypes.BOOL),
        OpenApiParameter("archived", OpenApiTypes.STR, enum=("false", "true", "all")),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=TimeEntryCreateSerializer,
        responses={201: TimeEntrySerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=TimeEntryUpdateSerializer,
        responses={200: TimeEntrySerializer, 400: ApiErrorResponseSerializer, 409: ApiErrorResponseSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "create":
            return TimeEntryCreateSerializer
        if self.action in {"update", "partial_update"}:
            return TimeEntryUpdateSerializer
        return TimeEntrySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role != User.Role.ADMIN:
            queryset = queryset.filter(employee=self.request.user)
        elif employee := self.request.query_params.get("employee"):
            queryset = queryset.filter(employee_id=employee)
        if self.action == "list":
            if value := self.request.query_params.get("date_from"):
                queryset = queryset.filter(work_date__gte=value)
            if value := self.request.query_params.get("date_to"):
                queryset = queryset.filter(work_date__lte=value)
            if value := self.request.query_params.get("project"):
                queryset = queryset.filter(project_id=value)
            if value := self.request.query_params.get("billable"):
                queryset = queryset.filter(billable=value.lower() == "true")
            archived = self.request.query_params.get("archived", "false").lower()
            if archived != "all":
                queryset = queryset.filter(archived_at__isnull=archived != "true")
        return queryset

    @extend_schema(request=None, responses={200: TimeEntrySerializer, 400: ApiErrorResponseSerializer})
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        try:
            entry = archive_time_entry(self.get_object().pk, request.user)
        except ValueError as error:
            return Response({"error": {"code": "invalid_state", "message": str(error)}}, status=400)
        return Response(TimeEntrySerializer(entry).data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: TimeEntryAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        return Response(
            TimeEntryAuditEventSerializer(self.get_object().audit_events.all(), many=True).data
        )


class ServiceEntryViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ServiceEntry.objects.select_related(
        "employee", "project", "work_package", "catalog_item"
    )
    pagination_class = TimeEntryPagination
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(parameters=[
        OpenApiParameter("date_from", OpenApiTypes.DATE),
        OpenApiParameter("date_to", OpenApiTypes.DATE),
        OpenApiParameter("project", OpenApiTypes.UUID),
        OpenApiParameter("employee", OpenApiTypes.INT, description="Nur für Administratoren"),
        OpenApiParameter("billable", OpenApiTypes.BOOL),
        OpenApiParameter("archived", OpenApiTypes.STR, enum=("false", "true", "all")),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=ServiceEntryCreateSerializer,
        responses={201: ServiceEntrySerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=ServiceEntryUpdateSerializer,
        responses={200: ServiceEntrySerializer, 400: ApiErrorResponseSerializer, 409: ApiErrorResponseSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "create":
            return ServiceEntryCreateSerializer
        if self.action in {"update", "partial_update"}:
            return ServiceEntryUpdateSerializer
        return ServiceEntrySerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role != User.Role.ADMIN:
            queryset = queryset.filter(employee=self.request.user)
        elif employee := self.request.query_params.get("employee"):
            queryset = queryset.filter(employee_id=employee)
        if self.action == "list":
            if value := self.request.query_params.get("date_from"):
                queryset = queryset.filter(service_date__gte=value)
            if value := self.request.query_params.get("date_to"):
                queryset = queryset.filter(service_date__lte=value)
            if value := self.request.query_params.get("project"):
                queryset = queryset.filter(project_id=value)
            if value := self.request.query_params.get("billable"):
                queryset = queryset.filter(billable=value.lower() == "true")
            archived = self.request.query_params.get("archived", "false").lower()
            if archived != "all":
                queryset = queryset.filter(archived_at__isnull=archived != "true")
        return queryset

    @extend_schema(
        request=None, responses={200: ServiceEntrySerializer, 400: ApiErrorResponseSerializer}
    )
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        try:
            entry = archive_service_entry(self.get_object().pk, request.user)
        except ValueError as error:
            return Response(
                {"error": {"code": "invalid_state", "message": str(error)}}, status=400
            )
        return Response(ServiceEntrySerializer(entry).data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: ServiceEntryAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        return Response(
            ServiceEntryAuditEventSerializer(
                self.get_object().audit_events.all(), many=True
            ).data
        )


class ProjectTimeSummaryView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]

    @extend_schema(
        parameters=[OpenApiParameter("project", OpenApiTypes.UUID, required=True)],
        responses={200: ProjectTimeSummarySerializer, 400: ApiErrorResponseSerializer},
    )
    def get(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            return Response(
                {"error": {"code": "validation_error", "message": "Projekt fehlt.", "fields": {"project": ["Dieses Feld ist erforderlich."]}}},
                status=400,
            )
        project = get_object_or_404(Project, pk=project_id)
        return Response(ProjectTimeSummarySerializer(project_time_summary(project)).data)


REPORT_PARAMETERS = [
    OpenApiParameter("date_from", OpenApiTypes.DATE, description="Standard: erster Tag des aktuellen Monats"),
    OpenApiParameter("date_to", OpenApiTypes.DATE, description="Standard: heute"),
    OpenApiParameter("project", OpenApiTypes.UUID),
    OpenApiParameter("employee", OpenApiTypes.INT, description="Nur für Administratoren"),
]


def _report_from_request(request):
    filters = TimeReportFilterSerializer(data=request.query_params)
    filters.is_valid(raise_exception=True)
    values = filters.validated_data
    return build_time_report(
        request.user,
        date_from=values["date_from"],
        date_to=values["date_to"],
        project_id=values.get("project"),
        employee_id=values.get("employee"),
    )


class TimeReportView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]

    @extend_schema(
        parameters=REPORT_PARAMETERS,
        responses={200: TimeReportSerializer, 400: ApiErrorResponseSerializer},
    )
    def get(self, request):
        return Response(TimeReportSerializer(_report_from_request(request)).data)


def _csv_decimal(value, decimal_places):
    if value is None:
        return ""
    return f"{value:.{decimal_places}f}".replace(".", ",")


def _csv_text(value):
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


class TimeReportExportView(APIView):
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]

    @extend_schema(
        parameters=REPORT_PARAMETERS,
        responses={
            (200, "text/csv"): OpenApiResponse(description="Excel-kompatibler CSV-Export"),
            400: ApiErrorResponseSerializer,
        },
    )
    def get(self, request):
        report = _report_from_request(request)
        stream = StringIO()
        writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
        writer.writerow([
            "Art", "Datum", "Mitarbeiter", "Projektnummer", "Projekt", "Arbeitspaket",
            "Beschreibung", "Stunden", "Menge", "Einheit", "Abrechenbar", "Nettowert EUR",
            "Abrechnungsstatus",
        ])
        for row in report["rows"]:
            writer.writerow([
                "Zeit" if row["entry_type"] == "time" else "Leistung",
                row["date"].strftime("%d.%m.%Y"), _csv_text(row["employee_name"]),
                _csv_text(row["project_number"]), _csv_text(row["project_name"]),
                _csv_text(row["work_package_title"]), _csv_text(row["description"]),
                _csv_decimal(row["hours"], 2), _csv_decimal(row["quantity"], 3),
                _csv_text(row["unit"]),
                "Ja" if row["billable"] else "Nein", _csv_decimal(row["net_value"], 2),
                _csv_text(row["billing_status"]),
            ])
        filename = f'zeiterfassung-{report["date_from"]}-{report["date_to"]}.csv'
        response = HttpResponse("\ufeff" + stream.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
