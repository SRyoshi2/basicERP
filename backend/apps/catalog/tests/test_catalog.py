from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.catalog.models import CatalogAuditEvent, CatalogItem


@pytest.fixture
def employee():
    return get_user_model().objects.create_user(
        username="catalog-user",
        email="catalog-user@example.test",
        password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def catalog_admin():
    return get_user_model().objects.create_user(
        username="catalog-admin",
        email="catalog-admin@example.test",
        password="test-password",
        role=get_user_model().Role.ADMIN,
    )


@pytest.fixture
def service_payload():
    today = date.today()
    return {
        "kind": "service",
        "name": "Beratung",
        "description": "Fachberatung pro Stunde",
        "unit": "hour",
        "tax_rate": "19.00",
        "tax_note": "",
        "prices": [{"net_amount": "120.00", "valid_from": today.isoformat(), "valid_until": None}],
    }


@pytest.mark.django_db
def test_employee_creates_items_with_sequence_current_price_and_audit(
    api_client, employee, service_payload
):
    api_client.force_authenticate(employee)
    first = api_client.post(reverse("catalog-item-list"), service_payload, format="json")
    second = api_client.post(
        reverse("catalog-item-list"),
        {
            **service_payload,
            "kind": "product",
            "name": "Handbuch",
            "unit": "piece",
            "tax_rate": "7.00",
        },
        format="json",
    )

    assert first.status_code == 201
    assert first.data["item_number"] == "A-01001"
    assert first.data["current_price"]["net_amount"] == "120.00"
    assert second.data["item_number"] == "A-01002"
    event = CatalogAuditEvent.objects.get(item_id=first.data["id"])
    assert event.action == CatalogAuditEvent.Action.CREATED
    assert event.actor == employee


@pytest.mark.django_db
def test_price_periods_must_not_overlap(api_client, employee, service_payload):
    api_client.force_authenticate(employee)
    today = date.today()
    service_payload["prices"] = [
        {
            "net_amount": "100.00",
            "valid_from": today.isoformat(),
            "valid_until": (today + timedelta(days=30)).isoformat(),
        },
        {
            "net_amount": "120.00",
            "valid_from": (today + timedelta(days=20)).isoformat(),
            "valid_until": None,
        },
    ]

    response = api_client.post(reverse("catalog-item-list"), service_payload, format="json")

    assert response.status_code == 400
    assert "überschneiden" in response.data["error"]["fields"]["prices"][0]


@pytest.mark.django_db
def test_catalog_search_filters_and_future_price(api_client, employee, service_payload):
    api_client.force_authenticate(employee)
    tomorrow = date.today() + timedelta(days=1)
    service_payload["prices"] = [
        {"net_amount": "130.00", "valid_from": tomorrow.isoformat(), "valid_until": None}
    ]
    api_client.post(reverse("catalog-item-list"), service_payload, format="json")

    response = api_client.get(
        reverse("catalog-item-list"), {"search": "Fachberatung", "kind": "service", "unit": "hour"}
    )

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["current_price"] is None


@pytest.mark.django_db
def test_update_uses_optimistic_version_and_records_history(api_client, employee, service_payload):
    api_client.force_authenticate(employee)
    created = api_client.post(reverse("catalog-item-list"), service_payload, format="json").data
    detail = reverse("catalog-item-detail", args=[created["id"]])

    updated = api_client.patch(detail, {"name": "Strategieberatung", "version": 1}, format="json")
    conflict = api_client.patch(detail, {"name": "Veraltet", "version": 1}, format="json")
    history = api_client.get(reverse("catalog-item-history", args=[created["id"]]))

    assert updated.status_code == 200
    assert updated.data["version"] == 2
    assert conflict.status_code == 409
    assert conflict.data["error"]["code"] == "version_conflict"
    assert [event["action"] for event in history.data] == ["updated", "created"]


@pytest.mark.django_db
def test_only_admin_can_archive_catalog_item(api_client, employee, catalog_admin, service_payload):
    api_client.force_authenticate(employee)
    created = api_client.post(reverse("catalog-item-list"), service_payload, format="json").data
    archive_url = reverse("catalog-item-archive", args=[created["id"]])
    assert api_client.post(archive_url).status_code == 403

    api_client.force_authenticate(catalog_admin)
    archived = api_client.post(archive_url)
    active = api_client.get(reverse("catalog-item-list"))
    archived_list = api_client.get(reverse("catalog-item-list"), {"archived": "true"})

    assert archived.status_code == 200
    assert archived.data["archived_at"] is not None
    assert active.data["count"] == 0
    assert archived_list.data["count"] == 1
    assert CatalogItem.objects.get(pk=created["id"]).version == 2


@pytest.mark.django_db
def test_catalog_requires_price_and_rejects_negative_amount(api_client, employee, service_payload):
    api_client.force_authenticate(employee)
    missing = api_client.post(
        reverse("catalog-item-list"), {**service_payload, "prices": []}, format="json"
    )
    negative = api_client.post(
        reverse("catalog-item-list"),
        {**service_payload, "prices": [{"net_amount": "-1.00", "valid_from": date.today()}]},
        format="json",
    )

    assert missing.status_code == 400
    assert negative.status_code == 400
