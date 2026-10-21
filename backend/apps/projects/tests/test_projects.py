import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.crm.models import Contact
from apps.projects.models import ProjectAuditEvent


@pytest.fixture
def employee():
    return get_user_model().objects.create_user(
        username="project-user", email="project-user@example.test", password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def project_admin():
    return get_user_model().objects.create_user(
        username="project-admin", email="project-admin@example.test", password="test-password",
        role=get_user_model().Role.ADMIN,
    )


@pytest.fixture
def customer(employee):
    return Contact.objects.create(
        customer_number="K-01001", kind=Contact.Kind.ORGANIZATION,
        company_name="Musterkunde GmbH", created_by=employee, updated_by=employee,
    )


@pytest.fixture
def payload(customer):
    return {
        "customer": str(customer.id), "name": "ERP-Einführung", "description": "Pilotprojekt",
        "status": "active", "start_date": "2026-10-01", "end_date": "2027-03-31",
        "budget_amount": "24000.00", "budget_hours": "200.00", "default_hourly_rate": "120.00",
    }


@pytest.mark.django_db
def test_employee_creates_project_with_number_customer_and_audit(api_client, employee, payload):
    api_client.force_authenticate(employee)
    first = api_client.post(reverse("project-list"), payload, format="json")
    second = api_client.post(reverse("project-list"), {**payload, "name": "Folgeprojekt"}, format="json")

    assert first.status_code == 201
    assert first.data["project_number"] == "P-01001"
    assert first.data["customer_name"] == "Musterkunde GmbH"
    assert second.data["project_number"] == "P-01002"
    event = ProjectAuditEvent.objects.get(project_id=first.data["id"])
    assert event.action == ProjectAuditEvent.Action.CREATED
    assert event.actor == employee


@pytest.mark.django_db
def test_project_validates_period_and_non_negative_budgets(api_client, employee, payload):
    api_client.force_authenticate(employee)
    bad_period = api_client.post(
        reverse("project-list"), {**payload, "start_date": "2026-10-02", "end_date": "2026-10-01"}, format="json"
    )
    bad_budget = api_client.post(reverse("project-list"), {**payload, "budget_hours": "-1.00"}, format="json")

    assert bad_period.status_code == 400
    assert "Enddatum" in bad_period.data["error"]["fields"]["end_date"][0]
    assert bad_budget.status_code == 400


@pytest.mark.django_db
def test_project_search_and_status_filter(api_client, employee, payload):
    api_client.force_authenticate(employee)
    api_client.post(reverse("project-list"), payload, format="json")

    result = api_client.get(reverse("project-list"), {"search": "Musterkunde", "status": "active"})
    empty = api_client.get(reverse("project-list"), {"status": "paused"})

    assert result.status_code == 200
    assert result.data["count"] == 1
    assert empty.data["count"] == 0


@pytest.mark.django_db
def test_update_uses_optimistic_version_and_records_history(api_client, employee, payload):
    api_client.force_authenticate(employee)
    created = api_client.post(reverse("project-list"), payload, format="json").data
    detail = reverse("project-detail", args=[created["id"]])

    updated = api_client.patch(detail, {"status": "paused", "version": 1}, format="json")
    conflict = api_client.patch(detail, {"name": "Veraltet", "version": 1}, format="json")
    history = api_client.get(reverse("project-history", args=[created["id"]]))

    assert updated.status_code == 200
    assert updated.data["version"] == 2
    assert conflict.status_code == 409
    assert [event["action"] for event in history.data] == ["updated", "created"]


@pytest.mark.django_db
def test_only_admin_can_archive_project(api_client, employee, project_admin, payload):
    api_client.force_authenticate(employee)
    created = api_client.post(reverse("project-list"), payload, format="json").data
    archive_url = reverse("project-archive", args=[created["id"]])
    assert api_client.post(archive_url).status_code == 403

    api_client.force_authenticate(project_admin)
    archived = api_client.post(archive_url)
    active = api_client.get(reverse("project-list"))

    assert archived.status_code == 200
    assert archived.data["archived_at"] is not None
    assert active.data["count"] == 0


@pytest.mark.django_db
def test_archived_customer_is_rejected(api_client, employee, customer, payload):
    customer.archived_at = timezone.now()
    customer.save(update_fields=("archived_at",))
    api_client.force_authenticate(employee)

    response = api_client.post(reverse("project-list"), payload, format="json")

    assert response.status_code == 400
    assert "Archivierte" in response.data["error"]["fields"]["customer"][0]
