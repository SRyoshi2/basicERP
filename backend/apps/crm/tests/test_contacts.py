import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.crm.models import Contact, ContactAuditEvent


@pytest.fixture
def employee():
    return get_user_model().objects.create_user(
        username="crm-user",
        email="crm-user@example.test",
        password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def crm_admin():
    return get_user_model().objects.create_user(
        username="crm-admin",
        email="crm-admin@example.test",
        password="test-password",
        role=get_user_model().Role.ADMIN,
    )


@pytest.fixture
def organization_payload():
    return {
        "kind": "organization",
        "company_name": "Nordlicht GmbH",
        "email": "kontakt@nordlicht.example",
        "addresses": [
            {
                "kind": "billing",
                "street": "Hafenstraße 1",
                "postal_code": "20457",
                "city": "Hamburg",
                "country_code": "de",
                "is_default": True,
            }
        ],
        "contact_persons": [
            {
                "first_name": "Nora",
                "last_name": "Nord",
                "role": "Einkauf",
                "email": "nora@nordlicht.example",
                "is_primary": True,
            }
        ],
    }


@pytest.mark.django_db
def test_employee_creates_contact_with_number_nested_data_and_audit(
    api_client, employee, organization_payload
):
    api_client.force_authenticate(employee)

    first = api_client.post(reverse("contact-list"), organization_payload, format="json")
    second_payload = {"kind": "person", "first_name": "Ada", "last_name": "Lovelace"}
    second = api_client.post(reverse("contact-list"), second_payload, format="json")

    assert first.status_code == 201
    assert first.data["customer_number"] == "K-01001"
    assert first.data["display_name"] == "Nordlicht GmbH"
    assert first.data["addresses"][0]["country_code"] == "DE"
    assert first.data["contact_persons"][0]["is_primary"] is True
    assert second.status_code == 201
    assert second.data["customer_number"] == "K-01002"
    event = ContactAuditEvent.objects.get(contact_id=first.data["id"])
    assert event.action == ContactAuditEvent.Action.CREATED
    assert event.actor == employee


@pytest.mark.django_db
def test_contact_list_supports_search_kind_and_pagination(api_client, employee, organization_payload):
    api_client.force_authenticate(employee)
    api_client.post(reverse("contact-list"), organization_payload, format="json")
    api_client.post(
        reverse("contact-list"),
        {"kind": "person", "first_name": "Grace", "last_name": "Hopper"},
        format="json",
    )

    response = api_client.get(reverse("contact-list"), {"search": "Nordlicht", "kind": "organization"})

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["results"][0]["company_name"] == "Nordlicht GmbH"


@pytest.mark.django_db
def test_update_uses_optimistic_version_and_records_history(
    api_client, employee, organization_payload
):
    api_client.force_authenticate(employee)
    created = api_client.post(reverse("contact-list"), organization_payload, format="json").data
    detail_url = reverse("contact-detail", args=[created["id"]])

    updated = api_client.patch(
        detail_url,
        {"version": created["version"], "company_name": "Nordlicht AG"},
        format="json",
    )
    conflict = api_client.patch(
        detail_url,
        {"version": created["version"], "company_name": "Veralteter Stand"},
        format="json",
    )

    assert updated.status_code == 200
    assert updated.data["version"] == 2
    assert conflict.status_code == 409
    assert conflict.data["error"]["code"] == "version_conflict"
    history = api_client.get(reverse("contact-history", args=[created["id"]]))
    assert [event["action"] for event in history.data] == ["updated", "created"]
    assert history.data[0]["changes"] == {"changed_fields": ["company_name"]}


@pytest.mark.django_db
def test_only_admin_can_archive_and_archived_contact_leaves_default_list(
    api_client, employee, crm_admin, organization_payload
):
    api_client.force_authenticate(employee)
    created = api_client.post(reverse("contact-list"), organization_payload, format="json").data
    archive_url = reverse("contact-archive", args=[created["id"]])

    forbidden = api_client.post(archive_url)
    assert forbidden.status_code == 403
    assert forbidden.data["error"]["code"] == "permission_denied"

    api_client.force_authenticate(crm_admin)
    archived = api_client.post(archive_url)
    active_list = api_client.get(reverse("contact-list"))
    archive_list = api_client.get(reverse("contact-list"), {"archived": "true"})

    assert archived.status_code == 200
    assert archived.data["archived_at"] is not None
    assert active_list.data["count"] == 0
    assert archive_list.data["count"] == 1
    assert Contact.objects.get(pk=created["id"]).version == 2


@pytest.mark.django_db
def test_contact_kind_and_nested_defaults_are_validated(api_client, employee):
    api_client.force_authenticate(employee)
    response = api_client.post(
        reverse("contact-list"),
        {
            "kind": "organization",
            "addresses": [
                {
                    "kind": "billing",
                    "street": "A 1",
                    "postal_code": "1",
                    "city": "A",
                    "is_default": True,
                },
                {
                    "kind": "billing",
                    "street": "B 2",
                    "postal_code": "2",
                    "city": "B",
                    "is_default": True,
                },
            ],
        },
        format="json",
    )

    assert response.status_code == 400
    fields = response.data["error"]["fields"]
    assert "company_name" in fields
    assert "addresses" in fields
