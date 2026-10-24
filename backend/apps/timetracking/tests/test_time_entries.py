from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import CatalogItem, CatalogPrice
from apps.crm.models import Contact
from apps.projects.models import Project, WorkPackage
from apps.timetracking.models import (
    ServiceEntry, ServiceEntryAuditEvent, TimeEntry, TimeEntryAuditEvent,
)


@pytest.fixture
def employee():
    return get_user_model().objects.create_user(
        username="time-user", email="time-user@example.test", password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def other_employee():
    return get_user_model().objects.create_user(
        username="other-time-user", email="other-time-user@example.test", password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def time_admin():
    return get_user_model().objects.create_user(
        username="time-admin", email="time-admin@example.test", password="test-password",
        role=get_user_model().Role.ADMIN,
    )


@pytest.fixture
def project(employee):
    customer = Contact.objects.create(
        customer_number="K-02001", kind=Contact.Kind.ORGANIZATION,
        company_name="Zeitkunde GmbH", created_by=employee, updated_by=employee,
    )
    return Project.objects.create(
        project_number="P-02001", customer=customer, name="Zeitprojekt", status="active",
        budget_amount="3000.00", budget_hours="20.00", default_hourly_rate="100.00",
        created_by=employee, updated_by=employee,
    )


@pytest.fixture
def work_package(project, employee):
    return WorkPackage.objects.create(
        project=project, title="Beratung", status="in_progress", planned_hours="12.00",
        assignee=employee, hourly_rate_override="125.00", created_by=employee, updated_by=employee,
    )


@pytest.fixture
def service_item(employee):
    item = CatalogItem.objects.create(
        item_number="L-02001", kind=CatalogItem.Kind.SERVICE, name="Workshop-Pauschale",
        unit=CatalogItem.Unit.FLAT, tax_rate="19.00", created_by=employee, updated_by=employee,
    )
    CatalogPrice.objects.create(
        item=item, net_amount="350.00", valid_from=date.today() - timedelta(days=30)
    )
    return item


def payload(project, work_package, **overrides):
    return {
        "project": str(project.id), "work_package": str(work_package.id),
        "work_date": date.today().isoformat(), "duration_minutes": 90,
        "description": "Anforderungsworkshop", "billable": True, **overrides,
    }


@pytest.mark.django_db
def test_employee_creates_own_time_with_rate_snapshot_and_audit(
    api_client, employee, project, work_package
):
    api_client.force_authenticate(employee)
    response = api_client.post(
        reverse("time-entry-list"), payload(project, work_package), format="json"
    )

    assert response.status_code == 201
    assert response.data["employee"] == employee.id
    assert response.data["duration_hours"] == "1.50"
    assert response.data["hourly_rate_snapshot"] == "125.00"
    assert response.data["billable_value"] == "187.50"
    event = TimeEntryAuditEvent.objects.get(time_entry_id=response.data["id"])
    assert event.action == TimeEntryAuditEvent.Action.CREATED
    assert event.actor == employee


@pytest.mark.django_db
def test_time_entry_rejects_invalid_duration_and_mismatched_package(
    api_client, employee, project, work_package
):
    other_customer = Contact.objects.create(
        customer_number="K-02002", kind=Contact.Kind.ORGANIZATION,
        company_name="Anderer Kunde", created_by=employee, updated_by=employee,
    )
    other_project = Project.objects.create(
        project_number="P-02002", customer=other_customer, name="Anderes Projekt",
        created_by=employee, updated_by=employee,
    )
    api_client.force_authenticate(employee)

    zero = api_client.post(
        reverse("time-entry-list"), payload(project, work_package, duration_minutes=0), format="json"
    )
    mismatch = api_client.post(
        reverse("time-entry-list"), payload(other_project, work_package), format="json"
    )

    assert zero.status_code == 400
    assert mismatch.status_code == 400
    assert "gehört nicht" in mismatch.data["error"]["fields"]["work_package"][0]


@pytest.mark.django_db
def test_employee_isolation_and_admin_overview(
    api_client, employee, other_employee, time_admin, project, work_package
):
    api_client.force_authenticate(employee)
    created = api_client.post(
        reverse("time-entry-list"), payload(project, work_package), format="json"
    ).data

    api_client.force_authenticate(other_employee)
    assert api_client.get(reverse("time-entry-detail", args=[created["id"]])).status_code == 404
    assert api_client.get(reverse("time-entry-list")).data["count"] == 0

    api_client.force_authenticate(time_admin)
    overview = api_client.get(reverse("time-entry-list"), {"employee": employee.id})
    assert overview.data["count"] == 1


@pytest.mark.django_db
def test_time_entry_update_uses_version_and_refreshes_rate_snapshot(
    api_client, employee, project, work_package
):
    second_package = WorkPackage.objects.create(
        project=project, title="Umsetzung", planned_hours="8.00",
        created_by=employee, updated_by=employee,
    )
    api_client.force_authenticate(employee)
    created = api_client.post(
        reverse("time-entry-list"), payload(project, work_package), format="json"
    ).data
    detail = reverse("time-entry-detail", args=[created["id"]])

    missing_version = api_client.patch(detail, {"description": "Ohne Version"}, format="json")
    updated = api_client.patch(
        detail,
        {"work_package": str(second_package.id), "description": "Umsetzung", "version": 1},
        format="json",
    )
    conflict = api_client.patch(detail, {"description": "Veraltet", "version": 1}, format="json")

    assert missing_version.status_code == 400
    assert "version" in missing_version.data["error"]["fields"]
    assert updated.status_code == 200
    assert updated.data["hourly_rate_snapshot"] == "100.00"
    assert updated.data["version"] == 2
    assert conflict.status_code == 409


@pytest.mark.django_db
def test_week_filter_archive_and_billed_lock(
    api_client, employee, project, work_package
):
    api_client.force_authenticate(employee)
    created = api_client.post(
        reverse("time-entry-list"), payload(project, work_package), format="json"
    ).data
    yesterday = date.today() - timedelta(days=1)
    weekly = api_client.get(
        reverse("time-entry-list"),
        {"date_from": yesterday.isoformat(), "date_to": date.today().isoformat()},
    )
    assert weekly.data["count"] == 1

    archived = api_client.post(reverse("time-entry-archive", args=[created["id"]]))
    assert archived.status_code == 200
    assert api_client.get(reverse("time-entry-list")).data["count"] == 0

    locked = TimeEntry.objects.get(pk=created["id"])
    locked.archived_at = None
    locked.billing_status = TimeEntry.BillingStatus.BILLED
    locked.save(update_fields=("archived_at", "billing_status"))
    rejected = api_client.patch(
        reverse("time-entry-detail", args=[created["id"]]),
        {"description": "Nicht erlaubt", "version": locked.version},
        format="json",
    )
    assert rejected.status_code == 400


@pytest.mark.django_db
def test_project_time_summary_separates_billable_and_non_billable(
    api_client, employee, project, work_package
):
    api_client.force_authenticate(employee)
    api_client.post(reverse("time-entry-list"), payload(project, work_package), format="json")
    api_client.post(
        reverse("time-entry-list"),
        payload(
            project, work_package, duration_minutes=30, description="Interne Abstimmung",
            billable=False,
        ),
        format="json",
    )

    summary = api_client.get(reverse("project-time-summary"), {"project": project.id})

    assert summary.status_code == 200
    assert summary.data == {
        "entry_count": 2,
        "actual_hours": "2.00",
        "billable_hours": "1.50",
        "unbilled_hours": "1.50",
        "non_billable_hours": "0.50",
        "actual_value": "187.50",
        "unbilled_value": "187.50",
        "remaining_budget_hours": "18.00",
        "remaining_budget_amount": "2812.50",
        "service_entry_count": 0,
        "service_value": "0.00",
        "unbilled_service_value": "0.00",
    }


def service_payload(project, work_package, service_item, **overrides):
    return {
        "project": str(project.id), "work_package": str(work_package.id),
        "catalog_item": str(service_item.id), "service_date": date.today().isoformat(),
        "quantity": "3.000", "description": "Drei Workshops", "billable": True,
        **overrides,
    }


@pytest.mark.django_db
def test_employee_creates_service_entry_with_complete_catalog_snapshot(
    api_client, employee, project, work_package, service_item
):
    api_client.force_authenticate(employee)
    response = api_client.post(
        reverse("service-entry-list"),
        service_payload(project, work_package, service_item),
        format="json",
    )

    assert response.status_code == 201
    assert response.data["employee"] == employee.id
    assert response.data["catalog_item_number_snapshot"] == "L-02001"
    assert response.data["catalog_item_name_snapshot"] == "Workshop-Pauschale"
    assert response.data["unit_snapshot"] == "flat"
    assert response.data["unit_price_snapshot"] == "350.00"
    assert response.data["tax_rate_snapshot"] == "19.00"
    assert response.data["total_net"] == "1050.00"
    assert ServiceEntryAuditEvent.objects.get(
        service_entry_id=response.data["id"]
    ).action == ServiceEntryAuditEvent.Action.CREATED


@pytest.mark.django_db
def test_service_entry_rejects_product_missing_price_and_invalid_quantity(
    api_client, employee, project, work_package, service_item
):
    product = CatalogItem.objects.create(
        item_number="A-02002", kind=CatalogItem.Kind.PRODUCT, name="Gerät",
        unit=CatalogItem.Unit.PIECE, tax_rate="19.00", created_by=employee, updated_by=employee,
    )
    CatalogPrice.objects.create(item=product, net_amount="25.00", valid_from=date.today())
    api_client.force_authenticate(employee)

    invalid_quantity = api_client.post(
        reverse("service-entry-list"),
        service_payload(project, work_package, service_item, quantity="0"), format="json",
    )
    product_response = api_client.post(
        reverse("service-entry-list"),
        service_payload(project, work_package, product), format="json",
    )
    missing_price = api_client.post(
        reverse("service-entry-list"),
        service_payload(
            project, work_package, service_item,
            service_date=(date.today() - timedelta(days=60)).isoformat(),
        ), format="json",
    )

    assert invalid_quantity.status_code == 400
    assert product_response.status_code == 400
    assert missing_price.status_code == 400


@pytest.mark.django_db
def test_service_entry_isolation_version_archive_and_billed_lock(
    api_client, employee, other_employee, time_admin, project, work_package, service_item
):
    api_client.force_authenticate(employee)
    created = api_client.post(
        reverse("service-entry-list"),
        service_payload(project, work_package, service_item), format="json",
    ).data
    detail = reverse("service-entry-detail", args=[created["id"]])

    api_client.force_authenticate(other_employee)
    assert api_client.get(detail).status_code == 404

    api_client.force_authenticate(employee)
    missing_version = api_client.patch(detail, {"quantity": "2.000"}, format="json")
    updated = api_client.patch(
        detail, {"quantity": "2.000", "version": 1}, format="json"
    )
    conflict = api_client.patch(
        detail, {"quantity": "1.000", "version": 1}, format="json"
    )
    assert missing_version.status_code == 400
    assert updated.status_code == 200
    assert updated.data["total_net"] == "700.00"
    assert conflict.status_code == 409

    archived = api_client.post(reverse("service-entry-archive", args=[created["id"]]))
    assert archived.status_code == 200
    assert api_client.get(reverse("service-entry-list")).data["count"] == 0

    locked = ServiceEntry.objects.get(pk=created["id"])
    locked.archived_at = None
    locked.billing_status = ServiceEntry.BillingStatus.BILLED
    locked.save(update_fields=("archived_at", "billing_status"))
    rejected = api_client.patch(
        detail, {"quantity": "1.000", "version": locked.version}, format="json"
    )
    assert rejected.status_code == 400

    api_client.force_authenticate(time_admin)
    assert api_client.get(reverse("service-entry-list"), {"employee": employee.id}).data[
        "count"
    ] == 1


@pytest.mark.django_db
def test_service_entries_extend_project_value_summary(
    api_client, employee, project, work_package, service_item
):
    api_client.force_authenticate(employee)
    api_client.post(
        reverse("service-entry-list"),
        service_payload(project, work_package, service_item, quantity="2.000"), format="json",
    )
    api_client.post(
        reverse("service-entry-list"),
        service_payload(
            project, work_package, service_item, quantity="1.000", billable=False,
            description="Kulanz",
        ), format="json",
    )

    summary = api_client.get(reverse("project-time-summary"), {"project": project.id})

    assert summary.status_code == 200
    assert summary.data["service_entry_count"] == 2
    assert summary.data["service_value"] == "700.00"
    assert summary.data["unbilled_service_value"] == "700.00"
    assert summary.data["actual_value"] == "700.00"
    assert summary.data["remaining_budget_amount"] == "2300.00"
