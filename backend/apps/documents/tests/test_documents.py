import io
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.storage import storages
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfWriter

from apps.catalog.models import CatalogItem
from apps.core.models import CompanyProfile
from apps.crm.models import Address, Contact
from apps.documents.artifacts import process_artifact_event
from apps.documents.calculations import calculate_document
from apps.documents.models import (
    BusinessDocument, BusinessDocumentAuditEvent, DocumentArtifact,
    DocumentNumberSequence, DocumentOutboxEvent, DocumentSnapshot,
)
from apps.projects.models import Project, WorkPackage
from apps.timetracking.models import (
    ServiceEntry, ServiceEntryAuditEvent, TimeEntry, TimeEntryAuditEvent,
)
from apps.timetracking.services import update_time_entry


@pytest.fixture
def document_admin():
    return get_user_model().objects.create_user(
        username="document-admin", email="document-admin@example.test",
        password="test-password", role=get_user_model().Role.ADMIN,
    )


@pytest.fixture(autouse=True)
def isolated_document_archive(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "archive": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": tmp_path / "archive"},
        },
    }
    storages._storages.clear()
    yield
    storages._storages.clear()


@pytest.fixture
def document_employee():
    return get_user_model().objects.create_user(
        username="document-employee", email="document-employee@example.test",
        password="test-password", role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def document_customer(document_admin):
    customer = Contact.objects.create(
        customer_number="K-04001", kind=Contact.Kind.ORGANIZATION,
        company_name="Belegkunde GmbH", created_by=document_admin, updated_by=document_admin,
    )
    Address.objects.create(
        contact=customer, kind=Address.Kind.BILLING, street="Teststraße 1",
        postal_code="10115", city="Berlin", country_code="DE", is_default=True,
    )
    return customer


@pytest.fixture
def other_document_customer(document_admin):
    return Contact.objects.create(
        customer_number="K-04002", kind=Contact.Kind.ORGANIZATION,
        company_name="Andere GmbH", created_by=document_admin, updated_by=document_admin,
    )


@pytest.fixture
def document_project(document_customer, document_admin):
    return Project.objects.create(
        project_number="P-04001", customer=document_customer, name="Belegprojekt",
        status=Project.Status.ACTIVE, created_by=document_admin, updated_by=document_admin,
    )


@pytest.fixture
def document_item(document_admin):
    return CatalogItem.objects.create(
        item_number="A-04001", kind=CatalogItem.Kind.SERVICE, name="Beratung",
        unit=CatalogItem.Unit.HOUR, tax_rate="19.00", created_by=document_admin,
        updated_by=document_admin,
    )


@pytest.fixture
def document_sources(document_admin, document_project, document_item):
    package = WorkPackage.objects.create(
        project=document_project, title="Umsetzung", status=WorkPackage.Status.IN_PROGRESS,
        planned_hours="10.00", hourly_rate_override="100.00",
        created_by=document_admin, updated_by=document_admin,
    )
    time_entry = TimeEntry.objects.create(
        employee=document_admin, project=document_project, work_package=package,
        work_date=date.today(), duration_minutes=481, description="Konzeption",
        billable=True, hourly_rate_snapshot="100.00", created_by=document_admin,
        updated_by=document_admin,
    )
    service_entry = ServiceEntry.objects.create(
        employee=document_admin, project=document_project, work_package=package,
        catalog_item=document_item, service_date=date.today(), quantity="2.000",
        description="Workshop", billable=True,
        catalog_item_number_snapshot=document_item.item_number,
        catalog_item_name_snapshot=document_item.name,
        unit_snapshot=document_item.unit, unit_price_snapshot="50.00",
        tax_rate_snapshot="19.00", created_by=document_admin, updated_by=document_admin,
    )
    return time_entry, service_entry


@pytest.fixture
def complete_company(document_admin):
    company, _ = CompanyProfile.objects.get_or_create(pk=1)
    company.legal_name = "Musterbüro GmbH"
    company.street = "Hauptstraße 10"
    company.postal_code = "10115"
    company.city = "Berlin"
    company.country_code = "DE"
    company.tax_number = "12/345/67890"
    company.updated_by = document_admin
    company.save()
    return company


def document_payload(customer, project, item=None, **overrides):
    payload = {
        "kind": "invoice", "customer": str(customer.id),
        "project": str(project.id) if project else None,
        "issue_date": date.today().isoformat(),
        "service_date_from": date.today().isoformat(),
        "service_date_to": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=14)).isoformat(),
        "tax_mode": "standard", "tax_exemption_note": "",
        "introduction": "Vielen Dank für Ihren Auftrag.",
        "closing_text": "Mit freundlichen Grüßen", "payment_terms": "Zahlbar in 14 Tagen.",
        "lines": [{
            "catalog_item": str(item.id) if item else None, "description": "Beratung",
            "quantity": "3.000", "unit": "hour", "unit_price_net": "100.00",
            "discount_percent": "10.00", "tax_rate": "19.00", "tax_note": "",
        }],
    }
    payload.update(overrides)
    return payload


def test_calculation_rounds_lines_then_tax_groups():
    lines = [
        SimpleNamespace(
            quantity=Decimal("3"), unit_price_net=Decimal("19.99"),
            discount_percent=Decimal("10"), tax_rate=Decimal("19"),
        ),
        SimpleNamespace(
            quantity=Decimal("1"), unit_price_net=Decimal("10"),
            discount_percent=Decimal("0"), tax_rate=Decimal("7"),
        ),
    ]
    result = calculate_document(lines)
    assert result["net_total"] == Decimal("63.97")
    assert result["tax_total"] == Decimal("10.95")
    assert result["gross_total"] == Decimal("74.92")
    assert result["tax_breakdown"] == [
        {
            "tax_rate": Decimal("7.00"), "net_amount": Decimal("10.00"),
            "tax_amount": Decimal("0.70"), "gross_amount": Decimal("10.70"),
        },
        {
            "tax_rate": Decimal("19.00"), "net_amount": Decimal("53.97"),
            "tax_amount": Decimal("10.25"), "gross_amount": Decimal("64.22"),
        },
    ]


@pytest.mark.django_db
def test_admin_creates_invoice_draft_with_totals_and_audit(
    api_client, document_admin, document_customer, document_project, document_item
):
    api_client.force_authenticate(document_admin)
    response = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project, document_item), format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["status"] == "draft"
    assert response.data["document_number"] is None
    assert response.data["net_total"] == "270.00"
    assert response.data["tax_total"] == "51.30"
    assert response.data["gross_total"] == "321.30"
    assert response.data["tax_breakdown"] == [{
        "tax_rate": "19.00", "net_amount": "270.00", "tax_amount": "51.30",
        "gross_amount": "321.30",
    }]
    document = BusinessDocument.objects.get(pk=response.data["id"])
    assert document.lines.count() == 1
    event = BusinessDocumentAuditEvent.objects.get(document=document)
    assert event.action == BusinessDocumentAuditEvent.Action.CREATED


@pytest.mark.django_db
def test_employee_cannot_access_documents(api_client, document_employee):
    api_client.force_authenticate(document_employee)
    assert api_client.get(reverse("business-document-list")).status_code == 403


@pytest.mark.django_db
def test_document_rejects_project_of_other_customer(
    api_client, document_admin, other_document_customer, document_project
):
    api_client.force_authenticate(document_admin)
    response = api_client.post(
        reverse("business-document-list"),
        document_payload(other_document_customer, document_project), format="json",
    )
    assert response.status_code == 400
    assert "Projekt gehört nicht" in response.data["error"]["fields"]["project"][0]


@pytest.mark.django_db
def test_small_business_document_requires_zero_tax_and_note(
    api_client, document_admin, document_customer, document_project
):
    api_client.force_authenticate(document_admin)
    payload = document_payload(
        document_customer, document_project, tax_mode="small_business",
        tax_exemption_note="",
    )
    response = api_client.post(reverse("business-document-list"), payload, format="json")
    assert response.status_code == 400
    assert "tax_exemption_note" in response.data["error"]["fields"]
    assert "lines" in response.data["error"]["fields"]


@pytest.mark.django_db
def test_valid_small_business_document_has_no_tax(
    api_client, document_admin, document_customer, document_project
):
    api_client.force_authenticate(document_admin)
    note = "Gemäß § 19 UStG wird keine Umsatzsteuer berechnet."
    payload = document_payload(
        document_customer, document_project, tax_mode="small_business",
        tax_exemption_note=note,
        lines=[{
            "catalog_item": None, "description": "Pauschale", "quantity": "1.000",
            "unit": "flat", "unit_price_net": "250.00", "discount_percent": "0.00",
            "tax_rate": "0.00", "tax_note": note,
        }],
    )
    response = api_client.post(reverse("business-document-list"), payload, format="json")
    assert response.status_code == 201, response.data
    assert response.data["net_total"] == "250.00"
    assert response.data["tax_total"] == "0.00"
    assert response.data["gross_total"] == "250.00"


@pytest.mark.django_db
def test_project_sources_can_be_reserved_released_and_cannot_be_edited(
    api_client, document_admin, document_customer, document_project, document_sources
):
    time_entry, service_entry = document_sources
    api_client.force_authenticate(document_admin)
    available = api_client.get(
        reverse("business-document-billable-items"), {"project": document_project.id}
    )
    assert available.status_code == 200, available.data
    assert {(item["source_type"], item["id"]) for item in available.data} == {
        ("time", str(time_entry.id)), ("service", str(service_entry.id)),
    }
    lines = [
        {
            "source_time_entry": str(time_entry.id), "source_service_entry": None,
            "catalog_item": None, "description": "Konzeption", "quantity": "1.000",
            "unit": "hour", "unit_price_net": "1.00", "discount_percent": "0.00",
            "tax_rate": "19.00", "tax_note": "",
        },
        {
            "source_time_entry": None, "source_service_entry": str(service_entry.id),
            "catalog_item": str(service_entry.catalog_item_id), "description": "Workshop",
            "quantity": "1.000", "unit": "hour", "unit_price_net": "1.00",
            "discount_percent": "0.00", "tax_rate": "19.00", "tax_note": "",
        },
    ]
    created = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project, lines=lines), format="json",
    )
    assert created.status_code == 201, created.data
    assert created.data["net_total"] == "901.67"
    assert created.data["gross_total"] == "1072.99"
    assert created.data["lines"][0]["quantity"] == "8.016667"
    assert created.data["lines"][0]["unit_price_net"] == "100.00"
    time_item = next(item for item in available.data if item["source_type"] == "time")
    assert time_item["net_amount"] == created.data["lines"][0]["net_amount"]
    with pytest.raises(ValueError, match="Rechnungsentwurf"):
        update_time_entry(
            time_entry.id,
            {
                "version": time_entry.version, "project": document_project,
                "work_package": time_entry.work_package, "work_date": time_entry.work_date,
                "duration_minutes": 60, "description": time_entry.description,
                "billable": True,
            },
            document_admin,
        )
    assert api_client.get(
        reverse("business-document-billable-items"), {"project": document_project.id}
    ).data == []
    duplicate = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project, lines=lines), format="json",
    )
    assert duplicate.status_code == 400
    archived = api_client.post(
        reverse("business-document-archive", args=(created.data["id"],)), {}, format="json"
    )
    assert archived.status_code == 200
    assert len(api_client.get(
        reverse("business-document-billable-items"), {"project": document_project.id}
    ).data) == 2


@pytest.mark.django_db
def test_finalization_marks_project_sources_billed_with_audit(
    api_client, document_admin, document_customer, document_project, document_sources,
    complete_company,
):
    time_entry, service_entry = document_sources
    api_client.force_authenticate(document_admin)
    lines = [
        {
            "source_time_entry": str(time_entry.id), "source_service_entry": None,
            "catalog_item": None, "description": "Konzeption", "quantity": "2.000",
            "unit": "hour", "unit_price_net": "100.00", "discount_percent": "0.00",
            "tax_rate": "19.00", "tax_note": "",
        },
        {
            "source_time_entry": None, "source_service_entry": str(service_entry.id),
            "catalog_item": str(service_entry.catalog_item_id), "description": "Workshop",
            "quantity": "2.000", "unit": "hour", "unit_price_net": "50.00",
            "discount_percent": "0.00", "tax_rate": "19.00", "tax_note": "",
        },
    ]
    created = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project, lines=lines), format="json",
    )
    finalized = api_client.post(
        reverse("business-document-finalize", args=(created.data["id"],)),
        {"version": created.data["version"]}, format="json",
    )
    assert finalized.status_code == 200, finalized.data
    time_entry.refresh_from_db()
    service_entry.refresh_from_db()
    assert time_entry.billing_status == TimeEntry.BillingStatus.BILLED
    assert service_entry.billing_status == ServiceEntry.BillingStatus.BILLED
    assert TimeEntryAuditEvent.objects.filter(
        time_entry=time_entry, action=TimeEntryAuditEvent.Action.BILLED
    ).exists()
    assert ServiceEntryAuditEvent.objects.filter(
        service_entry=service_entry, action=ServiceEntryAuditEvent.Action.BILLED
    ).exists()
    snapshot = DocumentSnapshot.objects.get(document_id=created.data["id"])
    assert snapshot.payload["lines"][0]["source_time_entry_id"] == str(time_entry.id)
    assert snapshot.payload["lines"][1]["source_service_entry_id"] == str(service_entry.id)


@pytest.mark.django_db
def test_update_replaces_lines_and_enforces_version(
    api_client, document_admin, document_customer, document_project
):
    api_client.force_authenticate(document_admin)
    create_response = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project), format="json",
    )
    document = BusinessDocument.objects.get(pk=create_response.data["id"])
    update_payload = document_payload(
        document_customer, document_project, kind="quote",
        lines=[{
            "catalog_item": None, "description": "Pauschale", "quantity": "1.000",
            "unit": "flat", "unit_price_net": "250.00", "discount_percent": "0.00",
            "tax_rate": "7.00", "tax_note": "",
        }],
    )
    update_payload["version"] = document.version
    response = api_client.patch(
        reverse("business-document-detail", args=(document.id,)), update_payload, format="json"
    )
    assert response.status_code == 200, response.data
    assert response.data["kind"] == "quote"
    assert response.data["gross_total"] == "267.50"
    assert response.data["version"] == 2

    stale = api_client.patch(
        reverse("business-document-detail", args=(document.id,)), update_payload, format="json"
    )
    assert stale.status_code == 409

    incomplete = api_client.patch(
        reverse("business-document-detail", args=(document.id,)),
        {"version": response.data["version"], "closing_text": "Ohne Positionen"}, format="json",
    )
    assert incomplete.status_code == 400
    assert "lines" in incomplete.data["error"]["fields"]


@pytest.mark.django_db
def test_admin_archives_draft(
    api_client, document_admin, document_customer, document_project
):
    api_client.force_authenticate(document_admin)
    created = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project), format="json",
    )
    response = api_client.post(
        reverse("business-document-archive", args=(created.data["id"],)), {}, format="json"
    )
    assert response.status_code == 200
    assert response.data["archived_at"] is not None
    assert not BusinessDocument.objects.filter(archived_at__isnull=True).exists()


@pytest.mark.django_db
def test_admin_finalizes_invoice_with_number_snapshot_audit_and_outbox(
    api_client, document_admin, document_customer, document_project, complete_company
):
    api_client.force_authenticate(document_admin)
    created = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project), format="json",
    )
    response = api_client.post(
        reverse("business-document-finalize", args=(created.data["id"],)),
        {"version": created.data["version"]}, format="json",
    )
    assert response.status_code == 200, response.data
    assert response.data["status"] == "finalizing"
    assert response.data["document_number"] == f"RE-{date.today().year}-0001"
    assert response.data["snapshot"]["schema_version"] == 1
    assert len(response.data["snapshot"]["sha256"]) == 64

    document = BusinessDocument.objects.get(pk=created.data["id"])
    snapshot = DocumentSnapshot.objects.get(document=document)
    assert snapshot.payload["issuer"]["name"] == "Musterbüro GmbH"
    assert snapshot.payload["recipient"]["street"] == "Teststraße 1"
    assert snapshot.payload["totals"]["gross_total"] == "321.30"
    assert snapshot.payload["lines"][0]["description"] == "Beratung"
    assert BusinessDocumentAuditEvent.objects.filter(
        document=document, action=BusinessDocumentAuditEvent.Action.FINALIZED
    ).exists()
    event = DocumentOutboxEvent.objects.get(document=document)
    assert event.status == DocumentOutboxEvent.Status.PENDING
    assert event.payload["snapshot_sha256"] == snapshot.sha256

    snapshot_response = api_client.get(
        reverse("business-document-snapshot", args=(document.id,))
    )
    assert snapshot_response.status_code == 200
    assert snapshot_response.data["payload"]["document_number"] == document.document_number

    snapshot.payload["document_number"] = "MANIPULIERT"
    with pytest.raises(ValidationError):
        snapshot.save()


@pytest.mark.django_db
def test_finalized_invoice_is_immutable_and_next_number_increments(
    api_client, document_admin, document_customer, document_project, complete_company
):
    api_client.force_authenticate(document_admin)
    numbers = []
    first_id = None
    for _ in range(2):
        created = api_client.post(
            reverse("business-document-list"),
            document_payload(document_customer, document_project), format="json",
        )
        finalized = api_client.post(
            reverse("business-document-finalize", args=(created.data["id"],)),
            {"version": created.data["version"]}, format="json",
        )
        assert finalized.status_code == 200, finalized.data
        numbers.append(finalized.data["document_number"])
        first_id = first_id or created.data["id"]
    assert numbers == [
        f"RE-{date.today().year}-0001", f"RE-{date.today().year}-0002",
    ]
    document = BusinessDocument.objects.get(pk=first_id)
    update_payload = document_payload(document_customer, document_project)
    update_payload["version"] = document.version
    update = api_client.patch(
        reverse("business-document-detail", args=(document.id,)), update_payload, format="json",
    )
    assert update.status_code == 400
    archive = api_client.post(
        reverse("business-document-archive", args=(document.id,)), {}, format="json",
    )
    assert archive.status_code == 400


@pytest.mark.django_db
def test_finalization_requires_complete_issuer_and_does_not_consume_number(
    api_client, document_admin, document_customer, document_project
):
    api_client.force_authenticate(document_admin)
    CompanyProfile.objects.get_or_create(pk=1)
    created = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project), format="json",
    )
    response = api_client.post(
        reverse("business-document-finalize", args=(created.data["id"],)),
        {"version": created.data["version"]}, format="json",
    )
    assert response.status_code == 400
    fields = response.data["error"]["fields"]
    assert {"company_name", "company_address", "company_tax_id"} <= set(fields)
    assert not DocumentNumberSequence.objects.exists()
    assert BusinessDocument.objects.get(pk=created.data["id"]).status == "draft"


@pytest.mark.django_db
def test_finalization_rejects_quote_and_customer_without_billing_address(
    api_client, document_admin, document_customer, document_project,
    other_document_customer, complete_company
):
    api_client.force_authenticate(document_admin)
    quote = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project, kind="quote"), format="json",
    )
    quote_response = api_client.post(
        reverse("business-document-finalize", args=(quote.data["id"],)),
        {"version": quote.data["version"]}, format="json",
    )
    assert quote_response.status_code == 400
    assert "kind" in quote_response.data["error"]["fields"]

    invoice = api_client.post(
        reverse("business-document-list"),
        document_payload(other_document_customer, None), format="json",
    )
    address_response = api_client.post(
        reverse("business-document-finalize", args=(invoice.data["id"],)),
        {"version": invoice.data["version"]}, format="json",
    )
    assert address_response.status_code == 400
    assert "customer_address" in address_response.data["error"]["fields"]


@pytest.mark.django_db
def test_artifact_event_archives_pdf_finalizes_document_and_downloads(
    api_client, document_admin, document_customer, document_project,
    complete_company, monkeypatch
):
    api_client.force_authenticate(document_admin)
    created = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project), format="json",
    )
    api_client.post(
        reverse("business-document-finalize", args=(created.data["id"],)),
        {"version": created.data["version"]}, format="json",
    )
    event = DocumentOutboxEvent.objects.get(document_id=created.data["id"])
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(stream)
    pdf_bytes = stream.getvalue()
    monkeypatch.setattr(
        "apps.documents.artifacts.render_invoice_pdf", lambda snapshot: pdf_bytes
    )

    artifact = process_artifact_event(event.id)
    assert artifact is not None
    document = BusinessDocument.objects.get(pk=created.data["id"])
    assert document.status == BusinessDocument.Status.FINALIZED
    assert DocumentArtifact.objects.filter(document=document).count() == 1
    event.refresh_from_db()
    assert event.status == DocumentOutboxEvent.Status.COMPLETED
    assert event.attempts == 1
    assert BusinessDocumentAuditEvent.objects.filter(
        document=document, action=BusinessDocumentAuditEvent.Action.ARTIFACT_CREATED
    ).exists()

    assert process_artifact_event(event.id) is None
    assert DocumentArtifact.objects.filter(document=document).count() == 1
    response = api_client.get(reverse("business-document-pdf", args=(document.id,)))
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == pdf_bytes


@pytest.mark.django_db
def test_failed_artifact_is_recorded_and_can_be_retried(
    api_client, document_admin, document_customer, document_project,
    complete_company, monkeypatch
):
    api_client.force_authenticate(document_admin)
    created = api_client.post(
        reverse("business-document-list"),
        document_payload(document_customer, document_project), format="json",
    )
    api_client.post(
        reverse("business-document-finalize", args=(created.data["id"],)),
        {"version": created.data["version"]}, format="json",
    )
    event = DocumentOutboxEvent.objects.get(document_id=created.data["id"])

    def fail(_snapshot):
        raise RuntimeError("Renderfehler im Test")

    monkeypatch.setattr("apps.documents.artifacts.render_invoice_pdf", fail)
    assert process_artifact_event(event.id) is None
    event.refresh_from_db()
    assert event.status == DocumentOutboxEvent.Status.FAILED
    assert "Renderfehler" in event.last_error
    assert event.available_at > timezone.now()
    assert BusinessDocument.objects.get(pk=created.data["id"]).status == "artifact_failed"

    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    writer.write(stream)
    monkeypatch.setattr(
        "apps.documents.artifacts.render_invoice_pdf", lambda snapshot: stream.getvalue()
    )
    artifact = process_artifact_event(event.id)
    assert artifact is not None
    event.refresh_from_db()
    assert event.status == DocumentOutboxEvent.Status.COMPLETED
    assert event.attempts == 2
    assert BusinessDocument.objects.get(pk=created.data["id"]).status == "finalized"
