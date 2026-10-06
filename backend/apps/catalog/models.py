import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class CatalogNumberSequence(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    next_value = models.PositiveBigIntegerField(default=1001)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_catalog_sequence")]


class CatalogItem(models.Model):
    class Kind(models.TextChoices):
        PRODUCT = "product", "Artikel"
        SERVICE = "service", "Leistung"

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
    item_number = models.CharField(max_length=24, unique=True, editable=False)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=16, choices=Unit.choices)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, choices=TAX_RATE_CHOICES)
    tax_note = models.CharField(max_length=240, blank=True)
    version = models.PositiveIntegerField(default=1)
    archived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_catalog_items"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="updated_catalog_items"
    )

    class Meta:
        ordering = ("item_number",)
        indexes = [models.Index(fields=("kind", "archived_at")), models.Index(fields=("name",))]

    def __str__(self):
        return f"{self.item_number} · {self.name}"


class CatalogPrice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(CatalogItem, on_delete=models.CASCADE, related_name="prices")
    net_amount = models.DecimalField(max_digits=12, decimal_places=2)
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ("-valid_from", "-id")
        constraints = [
            models.CheckConstraint(condition=models.Q(net_amount__gte=0), name="catalog_price_non_negative"),
            models.CheckConstraint(
                condition=models.Q(valid_until__isnull=True) | models.Q(valid_until__gte=models.F("valid_from")),
                name="catalog_price_valid_period",
            ),
            models.UniqueConstraint(fields=("item", "valid_from"), name="catalog_price_unique_start"),
        ]

    def clean(self):
        if self.net_amount < 0:
            raise ValidationError({"net_amount": "Der Nettopreis darf nicht negativ sein."})
        if self.valid_until and self.valid_until < self.valid_from:
            raise ValidationError({"valid_until": "Das Enddatum darf nicht vor dem Startdatum liegen."})


class CatalogAuditEvent(models.Model):
    class Action(models.TextChoices):
        CREATED = "created", "Erstellt"
        UPDATED = "updated", "Geändert"
        ARCHIVED = "archived", "Archiviert"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(CatalogItem, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=16, choices=Action.choices)
    version = models.PositiveIntegerField()
    changes = models.JSONField(default=dict)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="catalog_audit_events"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
