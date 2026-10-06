from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasCompletedPasswordChange, IsAdministrator
from apps.core.serializers import ApiErrorResponseSerializer

from .imports import apply_contact_import, preview_contact_import
from .models import Contact, ContactImportBatch
from .serializers import (
    ContactAuditEventSerializer,
    ContactCreateSerializer,
    ContactImportBatchSerializer,
    ContactImportUploadSerializer,
    ContactSerializer,
    ContactUpdateSerializer,
)
from .services import archive_contact


class ContactViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Contact.objects.prefetch_related("addresses", "contact_persons")
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(
        parameters=[
            OpenApiParameter("search", OpenApiTypes.STR, description="Name, E-Mail oder Kundennummer"),
            OpenApiParameter(
                "kind", OpenApiTypes.STR, enum=Contact.Kind.values, description="Firma oder Person"
            ),
            OpenApiParameter(
                "archived",
                OpenApiTypes.STR,
                enum=("false", "true", "all"),
                description="Aktive, archivierte oder alle Kontakte",
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=ContactCreateSerializer,
        responses={201: ContactSerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=ContactUpdateSerializer,
        responses={
            200: ContactSerializer,
            400: ApiErrorResponseSerializer,
            409: ApiErrorResponseSerializer,
        },
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
            return ContactCreateSerializer
        if self.action in {"update", "partial_update"}:
            return ContactUpdateSerializer
        return ContactSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            archived = self.request.query_params.get("archived", "false").lower()
            if archived != "all":
                queryset = queryset.filter(archived_at__isnull=archived != "true")
            kind = self.request.query_params.get("kind")
            if kind in Contact.Kind.values:
                queryset = queryset.filter(kind=kind)
            query = self.request.query_params.get("search", "").strip()[:100]
            if query:
                queryset = queryset.filter(
                    Q(customer_number__icontains=query)
                    | Q(company_name__icontains=query)
                    | Q(first_name__icontains=query)
                    | Q(last_name__icontains=query)
                    | Q(email__icontains=query)
                )
        return queryset

    @extend_schema(
        request=None,
        responses={200: ContactSerializer, 401: ApiErrorResponseSerializer, 403: ApiErrorResponseSerializer},
    )
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        contact = archive_contact(self.get_object().pk, request.user)
        return Response(ContactSerializer(contact).data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: ContactAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        contact = self.get_object()
        return Response(ContactAuditEventSerializer(contact.audit_events.all(), many=True).data)


class ContactImportViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ContactImportBatch.objects.all()
    serializer_class = ContactImportBatchSerializer
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "head", "options"]

    @extend_schema(
        request=ContactImportUploadSerializer,
        responses={200: ContactImportBatchSerializer, 400: ApiErrorResponseSerializer},
    )
    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser, FormParser])
    def preview(self, request):
        serializer = ContactImportUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        batch = preview_contact_import(serializer.validated_data["file"], request.user)
        return Response(ContactImportBatchSerializer(batch).data)

    @extend_schema(
        request=None,
        responses={200: ContactImportBatchSerializer, 400: ApiErrorResponseSerializer},
    )
    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        batch = apply_contact_import(self.get_object().pk, request.user)
        return Response(ContactImportBatchSerializer(batch).data)
