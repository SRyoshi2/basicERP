from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasCompletedPasswordChange, IsAdministrator
from apps.core.serializers import ApiErrorResponseSerializer

from .models import CatalogItem
from .serializers import (
    CatalogAuditEventSerializer,
    CatalogItemCreateSerializer,
    CatalogItemSerializer,
    CatalogItemUpdateSerializer,
)
from .services import archive_item


class CatalogItemViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = CatalogItem.objects.prefetch_related("prices")
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(
        parameters=[
            OpenApiParameter("search", OpenApiTypes.STR, description="Name, Beschreibung oder Nummer"),
            OpenApiParameter("kind", OpenApiTypes.STR, enum=CatalogItem.Kind.values),
            OpenApiParameter("unit", OpenApiTypes.STR, enum=CatalogItem.Unit.values),
            OpenApiParameter("archived", OpenApiTypes.STR, enum=("false", "true", "all")),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=CatalogItemCreateSerializer,
        responses={201: CatalogItemSerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(
        request=CatalogItemUpdateSerializer,
        responses={200: CatalogItemSerializer, 400: ApiErrorResponseSerializer, 409: ApiErrorResponseSerializer},
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
            return CatalogItemCreateSerializer
        if self.action in {"update", "partial_update"}:
            return CatalogItemUpdateSerializer
        return CatalogItemSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            archived = self.request.query_params.get("archived", "false").lower()
            if archived != "all":
                queryset = queryset.filter(archived_at__isnull=archived != "true")
            kind = self.request.query_params.get("kind")
            if kind in CatalogItem.Kind.values:
                queryset = queryset.filter(kind=kind)
            unit = self.request.query_params.get("unit")
            if unit in CatalogItem.Unit.values:
                queryset = queryset.filter(unit=unit)
            query = self.request.query_params.get("search", "").strip()[:100]
            if query:
                queryset = queryset.filter(
                    Q(item_number__icontains=query)
                    | Q(name__icontains=query)
                    | Q(description__icontains=query)
                )
        return queryset

    @extend_schema(request=None, responses={200: CatalogItemSerializer})
    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        item = archive_item(self.get_object().pk, request.user)
        return Response(CatalogItemSerializer(item).data, status=status.HTTP_200_OK)

    @extend_schema(responses={200: CatalogAuditEventSerializer(many=True)})
    @action(detail=True, methods=["get"], pagination_class=None)
    def history(self, request, pk=None):
        item = self.get_object()
        return Response(CatalogAuditEventSerializer(item.audit_events.all(), many=True).data)
