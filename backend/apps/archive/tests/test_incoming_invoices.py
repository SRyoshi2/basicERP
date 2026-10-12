import hashlib
import io

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from pypdf import PdfWriter

from apps.archive.models import ArchiveObject, IncomingInvoice


UBL_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
  <cbc:ID>RE-2026-1001</cbc:ID>
  <cbc:IssueDate>2026-10-12</cbc:IssueDate>
  <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
  <cac:AccountingSupplierParty><cac:Party><cac:PartyLegalEntity><cbc:RegistrationName>Lieferant GmbH</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingSupplierParty>
  <cac:AccountingCustomerParty><cac:Party><cac:PartyLegalEntity><cbc:RegistrationName>Kunde AG</cbc:RegistrationName></cac:PartyLegalEntity></cac:Party></cac:AccountingCustomerParty>
  <cac:LegalMonetaryTotal><cbc:PayableAmount currencyID="EUR">119.00</cbc:PayableAmount></cac:LegalMonetaryTotal>
</Invoice>"""

CII_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100" xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100" xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocument><ram:ID>CII-42</ram:ID><ram:IssueDateTime><udt:DateTimeString format="102">20261012</udt:DateTimeString></ram:IssueDateTime></rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement><ram:SellerTradeParty><ram:Name>Verkäufer KG</ram:Name></ram:SellerTradeParty><ram:BuyerTradeParty><ram:Name>Empfänger GmbH</ram:Name></ram:BuyerTradeParty></ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement><ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode><ram:SpecifiedTradeSettlementHeaderMonetarySummation><ram:DuePayableAmount>42.50</ram:DuePayableAmount></ram:SpecifiedTradeSettlementHeaderMonetarySummation></ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>""".encode()


@pytest.fixture
def invoice_user():
    return get_user_model().objects.create_user(
        username="invoice-user", email="invoice-user@example.test", password="test-password"
    )


@pytest.fixture(autouse=True)
def isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.STORAGES = {
        **settings.STORAGES,
        "archive": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": tmp_path / "archive"},
        },
    }


def upload(content, name, content_type):
    return SimpleUploadedFile(name, content, content_type=content_type)


@pytest.mark.django_db
def test_ubl_upload_preserves_original_extracts_metadata_and_is_idempotent(api_client, invoice_user):
    api_client.force_authenticate(invoice_user)
    first = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(UBL_XML, "rechnung.xml", "application/xml")},
        format="multipart",
    )
    second = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(UBL_XML, "kopie.xml", "application/xml")},
        format="multipart",
    )

    assert first.status_code == 201
    assert first.data["status"] == "valid"
    assert first.data["format"] == "xrechnung_ubl"
    assert first.data["invoice_number"] == "RE-2026-1001"
    assert first.data["seller_name"] == "Lieferant GmbH"
    assert first.data["buyer_name"] == "Kunde AG"
    assert first.data["payable_amount"] == "119.00"
    assert first.data["sha256"] == hashlib.sha256(UBL_XML).hexdigest()
    assert second.status_code == 200
    assert second.data["id"] == first.data["id"]
    assert ArchiveObject.objects.count() == 1
    archive = ArchiveObject.objects.get()
    with archive.file.open("rb") as stored:
        assert stored.read() == UBL_XML


@pytest.mark.django_db
def test_cii_upload_extracts_metadata(api_client, invoice_user):
    api_client.force_authenticate(invoice_user)
    response = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(CII_XML, "cii.xml", "application/xml")},
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["status"] == "valid"
    assert response.data["format"] == "xrechnung_cii"
    assert response.data["invoice_number"] == "CII-42"
    assert response.data["issue_date"] == "2026-10-12"
    assert response.data["payable_amount"] == "42.50"


@pytest.mark.django_db
def test_zugferd_pdf_extracts_embedded_xml(api_client, invoice_user):
    api_client.force_authenticate(invoice_user)
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.add_attachment("factur-x.xml", CII_XML)
    writer.write(output)

    response = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(output.getvalue(), "zugferd.pdf", "application/pdf")},
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["status"] == "valid"
    assert response.data["format"] == "zugferd"
    assert response.data["invoice_number"] == "CII-42"
    assert response.data["embedded_xml_sha256"] == hashlib.sha256(CII_XML).hexdigest()


@pytest.mark.django_db
def test_standard_pdf_can_be_recorded_with_manual_metadata(api_client, invoice_user):
    api_client.force_authenticate(invoice_user)
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(output)
    content = output.getvalue()

    response = api_client.post(
        reverse("incoming-invoice-list"),
        {
            "file": upload(content, "papier-rechnung.pdf", "application/pdf"),
            "mode": "standard_pdf",
            "invoice_number": "NORMAL-2026-7",
            "issue_date": "2026-10-11",
            "seller_name": "Papier & Co. KG",
            "buyer_name": "Kunde AG",
            "currency": "eur",
            "payable_amount": "23.80",
        },
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["format"] == "standard_pdf"
    assert response.data["status"] == "valid"
    assert response.data["invoice_number"] == "NORMAL-2026-7"
    assert response.data["currency"] == "EUR"
    assert response.data["validation_report"]["validator"] == "basicERP-manuell-v1"
    with ArchiveObject.objects.get().file.open("rb") as stored:
        assert stored.read() == content


@pytest.mark.django_db
def test_invalid_xml_is_safely_preserved_with_report(api_client, invoice_user):
    api_client.force_authenticate(invoice_user)
    unsafe = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><Invoice>&e;</Invoice>'

    response = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(unsafe, "unsafe.xml", "application/xml")},
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["status"] == "invalid"
    assert response.data["validation_report"]["passed"] is False
    assert any(
        error["code"] == "invalid_xml" for error in response.data["validation_report"]["errors"]
    )
    assert IncomingInvoice.objects.count() == 1


@pytest.mark.django_db
def test_original_can_be_downloaded_but_archive_object_is_immutable(api_client, invoice_user):
    api_client.force_authenticate(invoice_user)
    created = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(UBL_XML, "rechnung.xml", "application/xml")},
        format="multipart",
    ).data
    response = api_client.get(reverse("incoming-invoice-download", args=[created["id"]]))
    archive = ArchiveObject.objects.get()

    assert response.status_code == 200
    assert b"".join(response.streaming_content) == UBL_XML
    archive.original_name = "manipuliert.xml"
    with pytest.raises(ValidationError):
        archive.save()
    with pytest.raises(ValidationError):
        archive.delete()


@pytest.mark.django_db
def test_upload_rejects_unsupported_files_and_fake_pdf(api_client, invoice_user):
    api_client.force_authenticate(invoice_user)
    unsupported = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(b"text", "rechnung.txt", "text/plain")},
        format="multipart",
    )
    fake_pdf = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(b"not a pdf", "rechnung.pdf", "application/pdf")},
        format="multipart",
    )
    disguised_pdf = api_client.post(
        reverse("incoming-invoice-list"),
        {"file": upload(b"%PDF-disguised", "rechnung.xml", "application/xml")},
        format="multipart",
    )

    assert unsupported.status_code == 400
    assert fake_pdf.status_code == 400
    assert disguised_pdf.status_code == 400
    assert ArchiveObject.objects.count() == 0
