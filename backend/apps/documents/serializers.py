from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import (
    BusinessDocument, BusinessDocumentAuditEvent, DocumentLine, DocumentSnapshot,
)
from .services import create_document, update_document


TAX_RATE_CHOICES = (("19.00", "19 %"), ("7.00", "7 %"), ("0.00", "0 %"))


class DocumentLineSerializer(serializers.ModelSerializer):
    catalog_item_number = serializers.CharField(
        source="catalog_item.item_number", read_only=True, allow_null=True
    )
    catalog_item_name = serializers.CharField(
        source="catalog_item.name", read_only=True, allow_null=True
    )
    unit_label = serializers.CharField(source="get_unit_display", read_only=True)
    net_amount = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = DocumentLine
        fields = (
            "id", "position", "catalog_item", "catalog_item_number", "catalog_item_name",
            "description", "quantity", "unit", "unit_label", "unit_price_net",
            "discount_percent", "tax_rate", "tax_note", "net_amount",
        )


class DocumentLineWriteSerializer(serializers.ModelSerializer):
    quantity = serializers.DecimalField(
        max_digits=12, decimal_places=3, min_value=Decimal("0.001")
    )
    unit_price_net = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0")
    )
    discount_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0"), max_value=Decimal("100")
    )
    tax_rate = serializers.ChoiceField(choices=TAX_RATE_CHOICES)

    class Meta:
        model = DocumentLine
        fields = (
            "catalog_item", "description", "quantity", "unit", "unit_price_net",
            "discount_percent", "tax_rate", "tax_note",
        )

    def validate(self, attrs):
        item = attrs.get("catalog_item")
        if item and item.archived_at is not None:
            raise serializers.ValidationError(
                {"catalog_item": "Archivierte Katalogeinträge können nicht verwendet werden."}
            )
        if attrs["tax_rate"] == "0.00" and not attrs.get("tax_note", "").strip():
            raise serializers.ValidationError(
                {"tax_note": "Bei 0 % Steuer ist ein begründender Hinweis erforderlich."}
            )
        return attrs


class TaxBreakdownSerializer(serializers.Serializer):
    tax_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    net_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    tax_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    gross_amount = serializers.DecimalField(max_digits=18, decimal_places=2)


class DocumentSnapshotMetadataSerializer(serializers.Serializer):
    schema_version = serializers.IntegerField()
    calculation_version = serializers.IntegerField()
    sha256 = serializers.CharField()
    created_at = serializers.DateTimeField()


class DocumentSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentSnapshot
        fields = (
            "id", "schema_version", "calculation_version", "sha256", "payload",
            "created_at",
        )


class BusinessDocumentSerializer(serializers.ModelSerializer):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    customer_number = serializers.CharField(source="customer.customer_number", read_only=True)
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    project_number = serializers.CharField(
        source="project.project_number", read_only=True, allow_null=True
    )
    project_name = serializers.CharField(source="project.name", read_only=True, allow_null=True)
    lines = DocumentLineSerializer(many=True, read_only=True)
    net_total = serializers.SerializerMethodField()
    tax_total = serializers.SerializerMethodField()
    gross_total = serializers.SerializerMethodField()
    tax_breakdown = serializers.SerializerMethodField()
    snapshot = serializers.SerializerMethodField()

    class Meta:
        model = BusinessDocument
        fields = (
            "id", "kind", "kind_label", "status", "status_label", "document_number",
            "customer", "customer_number", "customer_name", "project", "project_number",
            "project_name", "issue_date", "service_date_from", "service_date_to", "due_date",
            "currency", "tax_mode", "tax_exemption_note", "introduction", "closing_text",
            "payment_terms", "lines", "net_total", "tax_total", "gross_total",
            "tax_breakdown", "snapshot", "version", "archived_at", "finalized_at",
            "created_at", "updated_at",
        )

    def _totals(self, obj):
        if not hasattr(obj, "_serializer_totals"):
            obj._serializer_totals = obj.totals
        return obj._serializer_totals

    @extend_schema_field(serializers.DecimalField(max_digits=18, decimal_places=2))
    def get_net_total(self, obj) -> str:
        return f"{self._totals(obj)['net_total']:.2f}"

    @extend_schema_field(serializers.DecimalField(max_digits=18, decimal_places=2))
    def get_tax_total(self, obj) -> str:
        return f"{self._totals(obj)['tax_total']:.2f}"

    @extend_schema_field(serializers.DecimalField(max_digits=18, decimal_places=2))
    def get_gross_total(self, obj) -> str:
        return f"{self._totals(obj)['gross_total']:.2f}"

    @extend_schema_field(TaxBreakdownSerializer(many=True))
    def get_tax_breakdown(self, obj) -> list:
        return TaxBreakdownSerializer(self._totals(obj)["tax_breakdown"], many=True).data

    @extend_schema_field(DocumentSnapshotMetadataSerializer(allow_null=True))
    def get_snapshot(self, obj) -> dict | None:
        snapshot = getattr(obj, "snapshot", None)
        if not snapshot:
            return None
        return DocumentSnapshotMetadataSerializer(snapshot).data


class BusinessDocumentWriteMixin(serializers.ModelSerializer):
    lines = DocumentLineWriteSerializer(many=True, min_length=1, max_length=100)

    class Meta:
        model = BusinessDocument
        fields = (
            "kind", "customer", "project", "issue_date", "service_date_from",
            "service_date_to", "due_date", "tax_mode", "tax_exemption_note",
            "introduction", "closing_text", "payment_terms", "lines",
        )

    def to_representation(self, instance):
        return BusinessDocumentSerializer(instance, context=self.context).data

    def validate(self, attrs):
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        project = attrs.get("project", getattr(self.instance, "project", None))
        issue_date = attrs.get("issue_date", getattr(self.instance, "issue_date", None))
        due_date = attrs.get("due_date", getattr(self.instance, "due_date", None))
        date_from = attrs.get(
            "service_date_from", getattr(self.instance, "service_date_from", None)
        )
        date_to = attrs.get("service_date_to", getattr(self.instance, "service_date_to", None))
        tax_mode = attrs.get("tax_mode", getattr(self.instance, "tax_mode", None))
        errors = {}
        lines = attrs.get("lines")
        if lines is None:
            errors["lines"] = "Für Änderungen müssen alle Positionen mitgesendet werden."
        if customer and customer.archived_at is not None:
            errors["customer"] = "Für archivierte Kunden können keine Belege angelegt werden."
        if project:
            if project.archived_at is not None:
                errors["project"] = "Archivierte Projekte können nicht verwendet werden."
            elif customer and project.customer_id != customer.id:
                errors["project"] = "Das Projekt gehört nicht zum gewählten Kunden."
        if date_from and date_to and date_to < date_from:
            errors["service_date_to"] = "Das Leistungsende darf nicht vor dem Leistungsbeginn liegen."
        if due_date and issue_date and due_date < issue_date:
            errors["due_date"] = "Das Fälligkeitsdatum darf nicht vor dem Belegdatum liegen."
        if tax_mode == BusinessDocument.TaxMode.SMALL_BUSINESS:
            if not attrs.get(
                "tax_exemption_note", getattr(self.instance, "tax_exemption_note", "")
            ).strip():
                errors["tax_exemption_note"] = "Für Kleinunternehmer ist ein Rechnungshinweis erforderlich."
            if any(line["tax_rate"] != "0.00" for line in (lines or [])):
                errors["lines"] = "Bei Kleinunternehmer-Belegen müssen alle Positionen 0 % Steuer haben."
        if self.instance and self.instance.archived_at is not None:
            errors["document"] = "Archivierte Belegentwürfe sind unveränderbar."
        if self.instance and self.instance.status != BusinessDocument.Status.DRAFT:
            errors["document"] = "Festgeschriebene Belege sind unveränderbar."
        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class BusinessDocumentCreateSerializer(BusinessDocumentWriteMixin):
    def create(self, validated_data):
        return create_document(validated_data, self.context["request"].user)


class BusinessDocumentUpdateSerializer(BusinessDocumentWriteMixin):
    version = serializers.IntegerField(min_value=1, required=True)

    class Meta(BusinessDocumentWriteMixin.Meta):
        fields = (*BusinessDocumentWriteMixin.Meta.fields, "version")

    def update(self, instance, validated_data):
        return update_document(instance.pk, validated_data, self.context["request"].user)


class BusinessDocumentAuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.CharField(source="actor.username", allow_null=True)

    class Meta:
        model = BusinessDocumentAuditEvent
        fields = ("id", "action", "version", "changes", "actor", "created_at")


class FinalizeDocumentSerializer(serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
