from rest_framework import serializers

from .models import IncomingInvoice


class IncomingInvoiceUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class IncomingInvoiceSerializer(serializers.ModelSerializer):
    original_name = serializers.CharField(source="archive_object.original_name", read_only=True)
    sha256 = serializers.CharField(source="archive_object.sha256", read_only=True)
    mime_type = serializers.CharField(source="archive_object.mime_type", read_only=True)
    size = serializers.IntegerField(source="archive_object.size", read_only=True)
    uploaded_by = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = IncomingInvoice
        fields = (
            "id",
            "status",
            "format",
            "invoice_number",
            "issue_date",
            "seller_name",
            "buyer_name",
            "currency",
            "payable_amount",
            "embedded_xml_sha256",
            "validation_report",
            "original_name",
            "sha256",
            "mime_type",
            "size",
            "uploaded_by",
            "download_url",
            "created_at",
        )
        read_only_fields = fields

    def get_uploaded_by(self, obj) -> str | None:
        return obj.created_by.username if obj.created_by else None

    def get_download_url(self, obj) -> str:
        return f"/api/v1/archive/incoming-invoices/{obj.pk}/download/"
