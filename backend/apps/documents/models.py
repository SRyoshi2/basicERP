import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .calculations import calculate_document, line_net


class BusinessDocument(models.Model):
    class Kind(models.TextChoices):
        QUOTE = "quote", "Angebot"
        INVOICE = "invoice", "Rechnung"

    class Status(models.TextChoices):
        DRAFT = "draft", "Entwurf"
        FINALIZING = "finalizing", "Festgeschrieben · PDF ausstehend"
        FINALIZED = "finalized", "Finalisiert"
        ARTIFACT_FAILED = "artifact_failed", "PDF-Erzeugung fehlgeschlagen"

    class TaxMode(models.TextChoices):
        STANDARD = "standard", "Regelbesteuerung"
        SMALL_BUSINESS = "small_business", "Kleinunternehmer (§ 19 UStG)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    document_number = models.CharField(max_length=40, null=True, blank=True, unique=True)
    customer = models.ForeignKey(
        "crm.Contact", on_delete=models.PROTECT, related_name="business_documents"
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.PROTECT,
        related_name="business_documents",
    )
    issue_date = models.DateField()
    service_date_from = models.DateField(null=True, blank=True)
    service_date_to = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR", editable=False)
    tax_mode = models.CharField(
        max_length=24, choices=TaxMode.choices, default=TaxMode.STANDARD
    )
    tax_exemption_note = models.CharField(
        max_length=300,
        blank=True,
        default="Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.",
    )
    introduction = models.TextField(blank=True)
    closing_text = models.TextField(blank=True)
    payment_terms = models.CharField(max_length=300, blank=True)
    version = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    finalized_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_business_documents",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="updated_business_documents",
    )
    finalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="finalized_business_documents",
    )

    class Meta:
        ordering = ("-issue_date", "-created_at")
        indexes = [
            models.Index(fields=("kind", "status", "archived_at")),
            models.Index(fields=("customer", "issue_date")),
            models.Index(fields=("project", "issue_date")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="draft", document_number__isnull=True,
                        finalized_at__isnull=True,
                    )
                    | models.Q(
                        status__in=("finalizing", "finalized", "artifact_failed"),
                        document_number__isnull=False,
                        finalized_at__isnull=False,
                    )
                ),
                name="document_finalization_fields_match_status",
            )
        ]

    def clean(self):
        errors = {}
        if self.customer_id and self.customer.archived_at is not None:
            errors["customer"] = "Für archivierte Kunden können keine Belege angelegt werden."
        if self.project_id:
            if self.project.archived_at is not None:
                errors["project"] = "Archivierte Projekte können nicht verwendet werden."
            elif self.customer_id and self.project.customer_id != self.customer_id:
                errors["project"] = "Das Projekt gehört nicht zum gewählten Kunden."
        if self.service_date_from and self.service_date_to:
            if self.service_date_to < self.service_date_from:
                errors["service_date_to"] = "Das Leistungsende darf nicht vor dem Leistungsbeginn liegen."
        if self.due_date and self.issue_date and self.due_date < self.issue_date:
            errors["due_date"] = "Das Fälligkeitsdatum darf nicht vor dem Belegdatum liegen."
        if self.tax_mode == self.TaxMode.SMALL_BUSINESS and not self.tax_exemption_note.strip():
            errors["tax_exemption_note"] = "Für Kleinunternehmer ist ein Rechnungshinweis erforderlich."
        if errors:
            raise ValidationError(errors)

    @property
    def totals(self):
        snapshot = getattr(self, "snapshot", None)
        if snapshot:
            totals = snapshot.payload["totals"]
            return {
                "net_total": Decimal(totals["net_total"]),
                "tax_total": Decimal(totals["tax_total"]),
                "gross_total": Decimal(totals["gross_total"]),
                "tax_breakdown": [
                    {key: Decimal(value) for key, value in group.items()}
                    for group in totals["tax_breakdown"]
                ],
            }
        return calculate_document(self.lines.all())


class DocumentNumberSequence(models.Model):
    kind = models.CharField(max_length=16, choices=BusinessDocument.Kind.choices)
    year = models.PositiveSmallIntegerField()
    prefix = models.CharField(max_length=12, default="RE")
    next_value = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("kind", "year"), name="document_number_sequence_kind_year"
            ),
            models.CheckConstraint(
                condition=models.Q(next_value__gt=0),
                name="document_number_sequence_next_positive",
            ),
        ]


class DocumentLine(models.Model):
    class Unit(models.TextChoices):
        HOUR = "hour", "Stunde"
        DAY = "day", "Tag"
        PIECE = "piece", "Stück"
        FLAT = "flat", "Pauschal"

    TAX_RATE_CHOICES = (
        (Decimal("19.00"), "19 %"),
        (Decimal("7.00"), "7 %"),
        (Decimal("0.00"), "0 %"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        BusinessDocument, on_delete=models.CASCADE, related_name="lines"
    )
    position = models.PositiveSmallIntegerField()
    catalog_item = models.ForeignKey(
        "catalog.CatalogItem", null=True, blank=True, on_delete=models.PROTECT,
        related_name="document_lines",
    )
    description = models.CharField(max_length=500)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=16, choices=Unit.choices)
    unit_price_net = models.DecimalField(max_digits=12, decimal_places=2)
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, choices=TAX_RATE_CHOICES
    )
    tax_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("position", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("document", "position"), name="document_line_unique_position"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="document_line_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price_net__gte=0),
                name="document_line_price_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_percent__gte=0)
                & models.Q(discount_percent__lte=100),
                name="document_line_discount_range",
            ),
        ]

    def clean(self):
        errors = {}
        if self.catalog_item_id and self.catalog_item.archived_at is not None:
            errors["catalog_item"] = "Archivierte Katalogeinträge können nicht verwendet werden."
        if self.tax_rate == 0 and not self.tax_note.strip():
            errors["tax_note"] = "Bei 0 % Steuer ist ein begründender Hinweis erforderlich."
        if self.document_id and self.document.tax_mode == BusinessDocument.TaxMode.SMALL_BUSINESS:
            if self.tax_rate != 0:
                errors["tax_rate"] = "Bei Kleinunternehmer-Belegen muss der Steuersatz 0 % sein."
        if errors:
            raise ValidationError(errors)

    @property
    def net_amount(self):
        return line_net(self.quantity, self.unit_price_net, self.discount_percent)


class BusinessDocumentAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Erstellt"
        UPDATED = "updated", "Geändert"
        ARCHIVED = "archived", "Archiviert"
        FINALIZED = "finalized", "Festgeschrieben"
        ARTIFACT_CREATED = "artifact_created", "PDF erzeugt"
        ARTIFACT_FAILED = "artifact_failed", "PDF fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        BusinessDocument, on_delete=models.PROTECT, related_name="audit_events"
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    version = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="business_document_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class DocumentSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField(
        BusinessDocument, on_delete=models.PROTECT, related_name="snapshot"
    )
    schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    calculation_version = models.PositiveSmallIntegerField(default=1, editable=False)
    payload = models.JSONField(editable=False)
    sha256 = models.CharField(max_length=64, unique=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="created_document_snapshots",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Ein festgeschriebener Belegsnapshot ist unveränderlich.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Ein festgeschriebener Belegsnapshot darf nicht gelöscht werden.")


class DocumentArtifact(models.Model):
    class Kind(models.TextChoices):
        STANDARD_PDF = "standard_pdf", "Standard-PDF"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        BusinessDocument, on_delete=models.PROTECT, related_name="artifacts"
    )
    snapshot = models.OneToOneField(
        DocumentSnapshot, on_delete=models.PROTECT, related_name="artifact"
    )
    archive_object = models.OneToOneField(
        "archive.ArchiveObject", on_delete=models.PROTECT,
        related_name="outgoing_document_artifact",
    )
    kind = models.CharField(
        max_length=24, choices=Kind.choices, default=Kind.STANDARD_PDF
    )
    renderer_version = models.CharField(max_length=40)
    template_version = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("document", "kind"), name="document_artifact_unique_kind"
            )
        ]


class DocumentOutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ausstehend"
        PROCESSING = "processing", "In Bearbeitung"
        COMPLETED = "completed", "Abgeschlossen"
        FAILED = "failed", "Fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        BusinessDocument, on_delete=models.PROTECT, related_name="outbox_events"
    )
    topic = models.CharField(max_length=80)
    event_key = models.CharField(max_length=160, unique=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("status", "available_at"))]
