from rest_framework import serializers

from .models import IncomingInvoice


class IncomingInvoiceUploadSerializer(serializers.Serializer):
    class Mode:
        AUTOMATIC = "automatic"
        STANDARD_PDF = "standard_pdf"

    file = serializers.FileField()
    mode = serializers.ChoiceField(
        choices=(
            (Mode.AUTOMATIC, "Automatische E-Rechnungsprüfung"),
            (Mode.STANDARD_PDF, "Normale PDF-Rechnung"),
        ),
        default=Mode.AUTOMATIC,
    )
    invoice_number = serializers.CharField(max_length=100, required=False)
    issue_date = serializers.DateField(required=False)
    seller_name = serializers.CharField(max_length=255, required=False)
    buyer_name = serializers.CharField(max_length=255, required=False)
    currency = serializers.RegexField(r"^[A-Za-z]{3}$", max_length=3, required=False)
    payable_amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)

    def validate(self, attrs):
        if attrs["mode"] != self.Mode.STANDARD_PDF:
            return attrs
        if not attrs["file"].name.lower().endswith(".pdf"):
            raise serializers.ValidationError(
                {"file": "Normale Rechnungen müssen als PDF hochgeladen werden."}
            )
        required = (
            "invoice_number",
            "issue_date",
            "seller_name",
            "buyer_name",
            "currency",
            "payable_amount",
        )
        errors = {
            field: "Dieses Feld ist für normale PDF-Rechnungen erforderlich."
            for field in required
            if attrs.get(field) in {None, ""}
        }
        if errors:
            raise serializers.ValidationError(errors)
        attrs["currency"] = attrs["currency"].upper()
        return attrs


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
