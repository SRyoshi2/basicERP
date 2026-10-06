import csv
import hashlib
import io
from copy import deepcopy

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import serializers

from .models import Contact, ContactImportBatch
from .services import create_contact


MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 5000
FIELD_ALIASES = {
    "kind": ("kind", "typ", "art", "type"),
    "company_name": ("company_name", "firma", "firmenname", "unternehmen"),
    "first_name": ("first_name", "vorname"),
    "last_name": ("last_name", "nachname"),
    "email": ("email", "e-mail", "mail"),
    "phone": ("phone", "telefon", "telefonnummer"),
    "street": ("street", "strasse", "straße", "anschrift"),
    "postal_code": ("postal_code", "plz", "postleitzahl"),
    "city": ("city", "ort", "stadt"),
    "country_code": ("country_code", "land", "laendercode", "ländercode"),
}


def _normalize_header(value):
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _mapped_value(row, field):
    for alias in FIELD_ALIASES[field]:
        value = row.get(_normalize_header(alias), "").strip()
        if value:
            return value
    return ""


def _normalize_kind(value):
    normalized = value.strip().lower()
    if normalized in {"firma", "unternehmen", "organization", "organisation"}:
        return Contact.Kind.ORGANIZATION
    if normalized in {"person", "privatperson"}:
        return Contact.Kind.PERSON
    return normalized


def _validate_row(raw_row, row_number):
    malformed = None in raw_row
    values = {
        _normalize_header(key or ""): (value or "").strip() if isinstance(value, str) else ""
        for key, value in raw_row.items()
    }
    payload = {
        "kind": _normalize_kind(_mapped_value(values, "kind")),
        "company_name": _mapped_value(values, "company_name"),
        "first_name": _mapped_value(values, "first_name"),
        "last_name": _mapped_value(values, "last_name"),
        "email": _mapped_value(values, "email"),
        "phone": _mapped_value(values, "phone"),
    }
    errors = {"row": ["Die Zeile enthält mehr Spalten als die Kopfzeile."]} if malformed else {}
    if payload["kind"] not in Contact.Kind.values:
        errors["kind"] = ["Erlaubt sind Firma oder Person."]
    elif payload["kind"] == Contact.Kind.ORGANIZATION and not payload["company_name"]:
        errors["company_name"] = ["Für Firmen ist der Firmenname erforderlich."]
    elif payload["kind"] == Contact.Kind.PERSON:
        if not payload["first_name"]:
            errors["first_name"] = ["Für Personen ist der Vorname erforderlich."]
        if not payload["last_name"]:
            errors["last_name"] = ["Für Personen ist der Nachname erforderlich."]

    email = serializers.EmailField(required=False, allow_blank=True)
    try:
        email.run_validation(payload["email"])
    except serializers.ValidationError:
        errors["email"] = ["Bitte eine gültige E-Mail-Adresse angeben."]

    address = {
        "kind": "billing",
        "street": _mapped_value(values, "street"),
        "postal_code": _mapped_value(values, "postal_code"),
        "city": _mapped_value(values, "city"),
        "country_code": (_mapped_value(values, "country_code") or "DE").upper(),
        "is_default": True,
    }
    address_values = (address["street"], address["postal_code"], address["city"])
    if any(address_values) and not all(address_values):
        errors["address"] = ["Straße, PLZ und Ort müssen gemeinsam angegeben werden."]
    if len(address["country_code"]) != 2:
        errors["country_code"] = ["Der Ländercode muss zweistellig sein."]
    payload["addresses"] = [address] if all(address_values) else []
    payload["contact_persons"] = []
    display_name = payload["company_name"] or " ".join(
        part for part in (payload["first_name"], payload["last_name"]) if part
    )
    return {"row_number": row_number, "display_name": display_name, "data": payload, "errors": errors}


def preview_contact_import(upload, actor):
    if upload.size > MAX_IMPORT_BYTES:
        raise serializers.ValidationError({"file": "Die CSV-Datei darf höchstens 5 MB groß sein."})
    content = upload.read()
    source_hash = hashlib.sha256(content).hexdigest()
    existing = ContactImportBatch.objects.filter(source_hash=source_hash).first()
    if existing:
        return existing
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise serializers.ValidationError({"file": "Die CSV-Datei muss UTF-8-codiert sein."}) from error
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise serializers.ValidationError({"file": "Die CSV-Datei enthält keine Kopfzeile."})
    normalized_headers = {_normalize_header(header) for header in reader.fieldnames if header}
    if not any(alias in normalized_headers for alias in FIELD_ALIASES["kind"]):
        raise serializers.ValidationError({"file": "Die Spalte 'Typ' oder 'kind' fehlt."})

    rows = []
    for row_number, row in enumerate(reader, start=2):
        if len(rows) >= MAX_IMPORT_ROWS:
            raise serializers.ValidationError({"file": "Pro Import sind höchstens 5.000 Zeilen erlaubt."})
        if not any((value or "").strip() for value in row.values()):
            continue
        rows.append(_validate_row(row, row_number))
    if not rows:
        raise serializers.ValidationError({"file": "Die CSV-Datei enthält keine Datenzeilen."})
    error_count = sum(1 for row in rows if row["errors"])
    try:
        return ContactImportBatch.objects.create(
            source_name=upload.name[:255],
            source_hash=source_hash,
            rows=rows,
            total_count=len(rows),
            valid_count=len(rows) - error_count,
            error_count=error_count,
            created_by=actor,
        )
    except IntegrityError:
        return ContactImportBatch.objects.get(source_hash=source_hash)


@transaction.atomic
def apply_contact_import(batch_id, actor):
    batch = ContactImportBatch.objects.select_for_update().get(pk=batch_id)
    if batch.status == ContactImportBatch.Status.COMPLETED:
        return batch
    if batch.error_count:
        raise serializers.ValidationError(
            {"rows": "Der Import enthält fehlerhafte Zeilen und kann noch nicht übernommen werden."}
        )
    contacts = []
    for row in batch.rows:
        contact = create_contact(deepcopy(row["data"]), actor)
        contacts.append({"id": str(contact.pk), "customer_number": contact.customer_number})
    batch.status = ContactImportBatch.Status.COMPLETED
    batch.created_count = len(contacts)
    batch.result = {"contacts": contacts}
    batch.completed_at = timezone.now()
    batch.save(update_fields=("status", "created_count", "result", "completed_at"))
    return batch
