import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .storage import get_archive_storage


def archive_upload_path(instance, filename):
    return f"objects/{instance.sha256[:2]}/{instance.sha256}"


class ArchiveObject(models.Model):
    class Source(models.TextChoices):
        INCOMING_INVOICE = "incoming_invoice", "E-Rechnungseingang"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(
        storage=get_archive_storage,
        upload_to=archive_upload_path,
        max_length=180,
    )
    sha256 = models.CharField(max_length=64, unique=True, editable=False)
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    source = models.CharField(max_length=32, choices=Source.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="created_archive_objects",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Archivobjekte sind unveränderbar.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Archivobjekte können nicht gelöscht werden.")


class IncomingInvoice(models.Model):
    class Format(models.TextChoices):
        STANDARD_PDF = "standard_pdf", "Normale PDF-Rechnung"
        XRECHNUNG_UBL = "xrechnung_ubl", "XRechnung UBL"
        XRECHNUNG_CII = "xrechnung_cii", "XRechnung CII"
        ZUGFERD = "zugferd", "ZUGFeRD"
        UNKNOWN = "unknown", "Unbekannt"

    class Status(models.TextChoices):
        VALID = "valid", "Basisprüfung bestanden"
        INVALID = "invalid", "Prüfung fehlgeschlagen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    archive_object = models.OneToOneField(
        ArchiveObject, on_delete=models.PROTECT, related_name="incoming_invoice"
    )
    format = models.CharField(max_length=24, choices=Format.choices, default=Format.UNKNOWN)
    status = models.CharField(max_length=16, choices=Status.choices)
    invoice_number = models.CharField(max_length=100, blank=True)
    issue_date = models.DateField(null=True, blank=True)
    seller_name = models.CharField(max_length=255, blank=True)
    buyer_name = models.CharField(max_length=255, blank=True)
    currency = models.CharField(max_length=3, blank=True)
    payable_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    embedded_xml_sha256 = models.CharField(max_length=64, blank=True)
    validation_report = models.JSONField(default=dict)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="incoming_invoices",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
