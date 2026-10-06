import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models


country_code_validator = RegexValidator(
    r"^[A-Z]{2}$", "Bitte einen zweistelligen ISO-Ländercode angeben."
)


class ContactNumberSequence(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_value = models.PositiveBigIntegerField(default=1001)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_contact_sequence")]


class Contact(models.Model):
    class Kind(models.TextChoices):
        ORGANIZATION = "organization", "Firma"
        PERSON = "person", "Person"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_number = models.CharField(max_length=24, unique=True, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    company_name = models.CharField(max_length=200, blank=True)
    salutation = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=50, blank=True)
    first_name = models.CharField(max_length=120, blank=True)
    last_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    vat_id = models.CharField(max_length=32, blank=True)
    leitweg_id = models.CharField(max_length=64, blank=True)
    version = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_contacts",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="updated_contacts",
    )

    class Meta:
        ordering = ("customer_number",)
        indexes = [
            models.Index(fields=("kind", "archived_at")),
            models.Index(fields=("company_name",)),
            models.Index(fields=("last_name", "first_name")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="organization") & ~models.Q(company_name="")
                    | models.Q(kind="person")
                    & ~models.Q(first_name="")
                    & ~models.Q(last_name="")
                ),
                name="contact_kind_required_names",
            )
        ]

    @property
    def display_name(self):
        if self.kind == self.Kind.ORGANIZATION:
            return self.company_name
        return " ".join(part for part in (self.title, self.first_name, self.last_name) if part)

    def clean(self):
        if self.kind == self.Kind.ORGANIZATION and not self.company_name.strip():
            raise ValidationError({"company_name": "Für Firmen ist der Firmenname erforderlich."})
        if self.kind == self.Kind.PERSON:
            errors = {}
            if not self.first_name.strip():
                errors["first_name"] = "Für Personen ist der Vorname erforderlich."
            if not self.last_name.strip():
                errors["last_name"] = "Für Personen ist der Nachname erforderlich."
            if errors:
                raise ValidationError(errors)

    def __str__(self):
        return f"{self.customer_number} · {self.display_name}"


class Address(models.Model):
    class Kind(models.TextChoices):
        BILLING = "billing", "Rechnung"
        SHIPPING = "shipping", "Lieferung"
        OTHER = "other", "Sonstige"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="addresses")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.BILLING)
    label = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=200)
    postal_code = models.CharField(max_length=20)
    city = models.CharField(max_length=120)
    country_code = models.CharField(max_length=2, default="DE", validators=[country_code_validator])
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ("kind", "label", "city")
        constraints = [
            models.UniqueConstraint(
                fields=("contact", "kind"),
                condition=models.Q(is_default=True),
                name="one_default_address_per_kind",
            )
        ]


class ContactPerson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="contact_persons")
    salutation = models.CharField(max_length=30, blank=True)
    title = models.CharField(max_length=50, blank=True)
    first_name = models.CharField(max_length=120)
    last_name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ("last_name", "first_name")
        constraints = [
            models.UniqueConstraint(
                fields=("contact",),
                condition=models.Q(is_primary=True),
                name="one_primary_contact_person",
            )
        ]


class ContactAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Erstellt"
        UPDATED = "updated", "Geändert"
        ARCHIVED = "archived", "Archiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=16, choices=Action.choices)
    version = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="contact_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class ContactImportBatch(models.Model):
    class Status(models.TextChoices):
        PREVIEW = "preview", "Geprüft"
        COMPLETED = "completed", "Übernommen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_name = models.CharField(max_length=255)
    source_hash = models.CharField(max_length=64, unique=True, editable=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PREVIEW)
    rows = models.JSONField(default=list)
    total_count = models.PositiveIntegerField(default=0)
    valid_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    result = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="contact_import_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
