import hashlib
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from django.core.files.base import ContentFile
from django.db import transaction
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rest_framework import serializers

from .models import ArchiveObject, IncomingInvoice


MAX_INVOICE_BYTES = 20 * 1024 * 1024
ZUGFERD_ATTACHMENT_NAMES = ("factur-x.xml", "zugferd-invoice.xml", "xrechnung.xml")


def _local_name(tag):
    return tag.rsplit("}", 1)[-1]


def _child(element, name):
    return next((child for child in element if _local_name(child.tag) == name), None)


def _path_text(root, path):
    current = root
    for name in path:
        current = _child(current, name)
        if current is None:
            return ""
    return (current.text or "").strip()


def _first_descendant_text(root, name):
    element = next((item for item in root.iter() if _local_name(item.tag) == name), None)
    return (element.text or "").strip() if element is not None else ""


def _parse_date(value, cii=False):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y%m%d" if cii else "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_amount(value):
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None


def _ubl_metadata(root):
    amount = _path_text(root, ("LegalMonetaryTotal", "PayableAmount"))
    return {
        "invoice_number": _path_text(root, ("ID",)),
        "issue_date": _parse_date(_path_text(root, ("IssueDate",))),
        "seller_name": _path_text(
            root, ("AccountingSupplierParty", "Party", "PartyLegalEntity", "RegistrationName")
        )
        or _path_text(root, ("AccountingSupplierParty", "Party", "PartyName", "Name")),
        "buyer_name": _path_text(
            root, ("AccountingCustomerParty", "Party", "PartyLegalEntity", "RegistrationName")
        )
        or _path_text(root, ("AccountingCustomerParty", "Party", "PartyName", "Name")),
        "currency": _path_text(root, ("DocumentCurrencyCode",)).upper(),
        "payable_amount": _parse_amount(amount),
    }


def _cii_metadata(root):
    date_value = _path_text(root, ("ExchangedDocument", "IssueDateTime", "DateTimeString"))
    amount = _first_descendant_text(root, "DuePayableAmount") or _first_descendant_text(
        root, "GrandTotalAmount"
    )
    return {
        "invoice_number": _path_text(root, ("ExchangedDocument", "ID")),
        "issue_date": _parse_date(date_value, cii=True),
        "seller_name": _path_text(
            root,
            (
                "SupplyChainTradeTransaction",
                "ApplicableHeaderTradeAgreement",
                "SellerTradeParty",
                "Name",
            ),
        ),
        "buyer_name": _path_text(
            root,
            (
                "SupplyChainTradeTransaction",
                "ApplicableHeaderTradeAgreement",
                "BuyerTradeParty",
                "Name",
            ),
        ),
        "currency": _first_descendant_text(root, "InvoiceCurrencyCode").upper(),
        "payable_amount": _parse_amount(amount),
    }


def _validate_metadata(invoice_format, metadata, parsing_errors=None):
    errors = list(parsing_errors or [])
    required = {
        "invoice_number": "Rechnungsnummer fehlt.",
        "issue_date": "Rechnungsdatum fehlt oder ist ungültig.",
        "seller_name": "Name des Verkäufers fehlt.",
        "buyer_name": "Name des Käufers fehlt.",
        "currency": "Rechnungswährung fehlt.",
        "payable_amount": "Zahlbetrag fehlt oder ist ungültig.",
    }
    if invoice_format == IncomingInvoice.Format.UNKNOWN:
        errors.append({"code": "unsupported_format", "message": "Kein unterstütztes Rechnungsformat erkannt."})
    for field, message in required.items():
        if metadata.get(field) in {None, ""}:
            errors.append({"code": f"missing_{field}", "field": field, "message": message})
    return {
        "validator": "basicERP-basis-v1",
        "scope": "Technische Basis- und Pflichtfeldprüfung; keine XSD-/Schematron- oder Rechtsprüfung.",
        "passed": not errors,
        "errors": errors,
    }


def _analyze_xml(xml_bytes, forced_format=None):
    empty = {
        "invoice_number": "",
        "issue_date": None,
        "seller_name": "",
        "buyer_name": "",
        "currency": "",
        "payable_amount": None,
    }
    try:
        root = ElementTree.fromstring(xml_bytes)
    except (ElementTree.ParseError, DefusedXmlException, ValueError) as error:
        report = _validate_metadata(
            IncomingInvoice.Format.UNKNOWN,
            empty,
            [{"code": "invalid_xml", "message": f"XML konnte nicht sicher gelesen werden: {error}"}],
        )
        return IncomingInvoice.Format.UNKNOWN, empty, report

    root_name = _local_name(root.tag)
    if root_name == "Invoice":
        detected_format = IncomingInvoice.Format.XRECHNUNG_UBL
        metadata = _ubl_metadata(root)
    elif root_name == "CrossIndustryInvoice":
        detected_format = IncomingInvoice.Format.XRECHNUNG_CII
        metadata = _cii_metadata(root)
    else:
        detected_format = IncomingInvoice.Format.UNKNOWN
        metadata = empty
    invoice_format = forced_format or detected_format
    report = _validate_metadata(invoice_format, metadata)
    report["xml_root"] = root_name
    report["detected_xml_format"] = detected_format
    return invoice_format, metadata, report


def _extract_pdf_xml(content):
    try:
        reader = PdfReader(io.BytesIO(content))
        attachments = reader.attachments
    except (PdfReadError, ValueError, TypeError) as error:
        return None, [{"code": "invalid_pdf", "message": f"PDF konnte nicht gelesen werden: {error}"}]
    lowered = {name.lower(): values for name, values in attachments.items()}
    for preferred in ZUGFERD_ATTACHMENT_NAMES:
        if preferred in lowered and lowered[preferred]:
            return lowered[preferred][0], []
    for name, values in lowered.items():
        if name.endswith(".xml") and values:
            return values[0], []
    return None, [
        {
            "code": "missing_embedded_xml",
            "message": "Das PDF enthält keine unterstützte eingebettete Rechnungs-XML.",
        }
    ]


def analyze_invoice(content, mime_type):
    if mime_type == "application/xml":
        invoice_format, metadata, report = _analyze_xml(content)
        return invoice_format, metadata, report, ""
    xml_bytes, pdf_errors = _extract_pdf_xml(content)
    if xml_bytes is None:
        metadata = {
            "invoice_number": "",
            "issue_date": None,
            "seller_name": "",
            "buyer_name": "",
            "currency": "",
            "payable_amount": None,
        }
        return (
            IncomingInvoice.Format.UNKNOWN,
            metadata,
            _validate_metadata(IncomingInvoice.Format.UNKNOWN, metadata, pdf_errors),
            "",
        )
    _, metadata, report = _analyze_xml(xml_bytes, forced_format=IncomingInvoice.Format.ZUGFERD)
    report["embedded_xml_sha256"] = hashlib.sha256(xml_bytes).hexdigest()
    return IncomingInvoice.Format.ZUGFERD, metadata, report, report["embedded_xml_sha256"]


@transaction.atomic
def ingest_invoice(upload, actor, manual_metadata=None):
    if upload.size > MAX_INVOICE_BYTES:
        raise serializers.ValidationError({"file": "Die Datei darf höchstens 20 MB groß sein."})
    original_name = Path(upload.name).name[:255]
    suffix = Path(original_name).suffix.lower()
    if suffix not in {".xml", ".pdf"}:
        raise serializers.ValidationError({"file": "Unterstützt werden XML- und PDF-Dateien."})
    content = upload.read()
    mime_type = "application/pdf" if content.startswith(b"%PDF-") else "application/xml"
    if suffix == ".pdf" and mime_type != "application/pdf":
        raise serializers.ValidationError({"file": "Die Datei besitzt keine gültige PDF-Signatur."})
    if suffix == ".xml" and mime_type == "application/pdf":
        raise serializers.ValidationError(
            {"file": "Dateiendung und Dateiinhalt passen nicht zusammen."}
        )

    digest = hashlib.sha256(content).hexdigest()
    existing = IncomingInvoice.objects.filter(archive_object__sha256=digest).first()
    if existing:
        return existing, False

    if manual_metadata is not None:
        if mime_type != "application/pdf":
            raise serializers.ValidationError(
                {"file": "Normale Rechnungen müssen als PDF hochgeladen werden."}
            )
        try:
            PdfReader(io.BytesIO(content))
        except (PdfReadError, ValueError, TypeError) as error:
            raise serializers.ValidationError(
                {"file": f"PDF konnte nicht gelesen werden: {error}"}
            ) from error
        invoice_format = IncomingInvoice.Format.STANDARD_PDF
        metadata = manual_metadata
        report = {
            "validator": "basicERP-manuell-v1",
            "scope": "Manuell erfasste Metadaten und lesbares PDF; keine inhaltliche oder rechtliche Rechnungsprüfung.",
            "passed": True,
            "errors": [],
        }
        embedded_hash = ""
    else:
        invoice_format, metadata, report, embedded_hash = analyze_invoice(content, mime_type)
    archive_object = ArchiveObject(
        sha256=digest,
        original_name=original_name,
        mime_type=mime_type,
        size=len(content),
        source=ArchiveObject.Source.INCOMING_INVOICE,
        created_by=actor,
    )
    archive_object.file.save(digest, ContentFile(content), save=False)
    archive_object.save()
    invoice = IncomingInvoice.objects.create(
        archive_object=archive_object,
        format=invoice_format,
        status=(IncomingInvoice.Status.VALID if report["passed"] else IncomingInvoice.Status.INVALID),
        embedded_xml_sha256=embedded_hash,
        validation_report=report,
        created_by=actor,
        **metadata,
    )
    return invoice, True
