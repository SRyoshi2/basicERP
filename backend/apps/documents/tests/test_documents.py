from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import CatalogItem
from apps.crm.models import Address, Contact
from apps.documents.calculations import calculate_document
from apps.documents.models import BusinessDocument, BusinessDocumentAuditEvent
from apps.projects.models import Project


@pytest.fixture
def document_admin():
    return get_user_model().objects.create_user(
        username="document-admin", email="document-admin@example.test",
        password="test-password", role=get_user_model().Role.ADMIN,
    )


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


def document_payload(customer, project, item=None, **overrides):
    payload = {
        "kind": "invoice", "customer": str(customer.id), "project": str(project.id),
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
