from django.db.models import Q
from django.http import FileResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import HasCompletedPasswordChange
from apps.core.serializers import ApiErrorResponseSerializer

from .models import IncomingInvoice
from .serializers import IncomingInvoiceSerializer, IncomingInvoiceUploadSerializer
from .services import ingest_invoice


class IncomingInvoiceViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = IncomingInvoice.objects.select_related("archive_object", "created_by")
    serializer_class = IncomingInvoiceSerializer
    permission_classes = [IsAuthenticated, HasCompletedPasswordChange]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ["get", "post", "head", "options"]

    @extend_schema(
        parameters=[
            OpenApiParameter("search", OpenApiTypes.STR, description="Nummer, Datei, Verkäufer oder Käufer"),
            OpenApiParameter("status", OpenApiTypes.STR, enum=IncomingInvoice.Status.values),
            OpenApiParameter("format", OpenApiTypes.STR, enum=IncomingInvoice.Format.values),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "list":
            status_value = self.request.query_params.get("status")
            if status_value in IncomingInvoice.Status.values:
                queryset = queryset.filter(status=status_value)
            format_value = self.request.query_params.get("format")
            if format_value in IncomingInvoice.Format.values:
                queryset = queryset.filter(format=format_value)
            query = self.request.query_params.get("search", "").strip()[:100]
            if query:
                queryset = queryset.filter(
                    Q(invoice_number__icontains=query)
                    | Q(seller_name__icontains=query)
                    | Q(buyer_name__icontains=query)
                    | Q(archive_object__original_name__icontains=query)
                )
        return queryset

    @extend_schema(
        request=IncomingInvoiceUploadSerializer,
        responses={201: IncomingInvoiceSerializer, 200: IncomingInvoiceSerializer, 400: ApiErrorResponseSerializer},
    )
    def create(self, request, *args, **kwargs):
        serializer = IncomingInvoiceUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice, created = ingest_invoice(serializer.validated_data["file"], request.user)
        return Response(
            IncomingInvoiceSerializer(invoice).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @extend_schema(responses={(200, "application/octet-stream"): OpenApiTypes.BINARY})
    @action(detail=True, methods=["get"], pagination_class=None)
    def download(self, request, pk=None):
        invoice = self.get_object()
        return FileResponse(
            invoice.archive_object.file.open("rb"),
            as_attachment=True,
            filename=invoice.archive_object.original_name,
            content_type=invoice.archive_object.mime_type,
        )
