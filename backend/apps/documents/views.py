from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import ValidationError

from apps.core.permissions import HasCompletedPasswordChange, IsAdministrator
from apps.core.serializers import ApiErrorResponseSerializer

from .models import BusinessDocument, DocumentArtifact, DocumentSnapshot
from .serializers import (
    BusinessDocumentAuditEventSerializer, BusinessDocumentCreateSerializer,
    BusinessDocumentSerializer, BusinessDocumentUpdateSerializer,
    DocumentSnapshotSerializer, FinalizeDocumentSerializer,
)
from .services import archive_document, finalize_document


class BusinessDocumentViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = BusinessDocument.objects.select_related(
        "customer", "project", "snapshot"
    ).prefetch_related("lines__catalog_item", "artifacts__archive_object")
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange, IsAdministrator]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(parameters=[
        OpenApiParameter("search", OpenApiTypes.STR, description="Kunde, Projektnummer oder Projektname"),
        OpenApiParameter("kind", OpenApiTypes.STR, enum=BusinessDocument.Kind.values),
        OpenApiParameter("customer", OpenApiTypes.UUID),
        OpenApiParameter("project", OpenApiTypes.UUID),
        OpenApiParameter("archived", OpenApiTypes.STR, enum=("false", "true", "all")),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=BusinessDocumentCreateSerializer,
        responses={201: BusinessDocumentSerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=BusinessDocumentUpdateSerializer,
        responses={
            200: BusinessDocumentSerializer,
            400: ApiErrorResponseSerializer,
            409: ApiErrorResponseSerializer,
        },
    )
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == "create":
            return BusinessDocumentCreateSerializer
        if self.action in {"update", "partial_update"}:
            return BusinessDocumentUpdateSerializer
        return BusinessDocumentSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            archived = self.request.query_params.get("archived", "false").lower()
            if archived != "all":
                queryset = queryset.filter(archived_at__isnull=archived != "true")
            kind = self.request.query_params.get("kind")
            if kind in BusinessDocument.Kind.values:
                queryset = queryset.filter(kind=kind)
            if customer := self.request.query_params.get("customer"):
                queryset = queryset.filter(customer_id=customer)
            if project := self.request.query_params.get("project"):
                queryset = queryset.filter(project_id=project)
            search = self.request.query_params.get("search", "").strip()[:100]
            if search:
                queryset = queryset.filter(
                    Q(customer__customer_number__icontains=search)
                    | Q(customer__company_name__icontains=search)
                    | Q(customer__first_name__icontains=search)
                    | Q(customer__last_name__icontains=search)
                    | Q(project__project_number__icontains=search)
                    | Q(project__name__icontains=search)
                )
        return queryset

    @extend_schema(
        request=None,
        responses={200: BusinessDocumentSerializer, 400: ApiErrorResponseSerializer},
    )
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        try:
            document = archive_document(self.get_object().pk, request.user)
        except ValueError as error:
            return Response(
                {"error": {"code": "invalid_state", "message": str(error)}}, status=400
            )
        return Response(BusinessDocumentSerializer(document).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=FinalizeDocumentSerializer,
        responses={
            200: BusinessDocumentSerializer,
            400: ApiErrorResponseSerializer,
            409: ApiErrorResponseSerializer,
        },
    )
    @action(detail=True, methods=["post"])
    def finalize(self, request, pk=None):
        request_serializer = FinalizeDocumentSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        try:
            document = finalize_document(
                self.get_object().pk,
                request_serializer.validated_data["version"],
                request.user,
            )
        except DjangoValidationError as error:
            raise ValidationError(error.message_dict) from error
        return Response(BusinessDocumentSerializer(document).data)

    @extend_schema(responses={200: DocumentSnapshotSerializer})
    @action(detail=True, methods=["get"], pagination_class=None)
    def snapshot(self, request, pk=None):
        document = self.get_object()
        try:
            snapshot = document.snapshot
        except DocumentSnapshot.DoesNotExist:
            return Response(
                {"error": {"code": "not_finalized", "message": "Der Beleg ist nicht festgeschrieben."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(DocumentSnapshotSerializer(snapshot).data)

    @extend_schema(responses={(200, "application/pdf"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"], pagination_class=None)
    def pdf(self, request, pk=None):
        document = self.get_object()
        artifact = document.artifacts.filter(
            kind=DocumentArtifact.Kind.STANDARD_PDF
        ).select_related("archive_object").first()
        if artifact is None:
            return Response(
                {
                    "error": {
                        "code": "pdf_not_ready",
                        "message": "Das Standard-PDF ist noch nicht verfügbar.",
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        return FileResponse(
            artifact.archive_object.file.open("rb"),
            as_attachment=True,
            filename=artifact.archive_object.original_name,
            content_type="application/pdf",
        )

    @extend_schema(responses={200: BusinessDocumentAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        return Response(
            BusinessDocumentAuditEventSerializer(
                self.get_object().audit_events.select_related("actor"), many=True
            ).data
        )
