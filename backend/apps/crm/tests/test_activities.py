import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.crm.models import ContactActivity


@pytest.fixture
def activity_user():
    return get_user_model().objects.create_user(
        username="activity-user",
        email="activity-user@example.test",
        password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def activity_admin():
    return get_user_model().objects.create_user(
        username="activity-admin",
        email="activity-admin@example.test",
        password="test-password",
        role=get_user_model().Role.ADMIN,
    )


def create_contact(api_client, name="Timeline GmbH"):
    return api_client.post(
        reverse("contact-list"), {"kind": "organization", "company_name": name}, format="json"
    ).data


@pytest.mark.django_db
def test_employee_creates_and_lists_contact_timeline(api_client, activity_user):
    api_client.force_authenticate(activity_user)
    contact = create_contact(api_client)
    occurred_at = timezone.now().isoformat()

    created = api_client.post(
        reverse("contact-activity-list"),
        {
            "contact": contact["id"],
            "kind": "call",
            "subject": "Erstgespräch",
            "body": "Bedarf und nächstes Vorgehen geklärt.",
            "occurred_at": occurred_at,
        },
        format="json",
    )
    timeline = api_client.get(reverse("contact-activity-list"), {"contact": contact["id"]})
    without_contact = api_client.get(reverse("contact-activity-list"))

    assert created.status_code == 201
    assert created.data["author"] == activity_user.username
    assert created.data["version"] == 1
    assert timeline.data["count"] == 1
    assert timeline.data["results"][0]["subject"] == "Erstgespräch"
    assert without_contact.data["count"] == 0


@pytest.mark.django_db
def test_activity_update_detects_stale_version(api_client, activity_user):
    api_client.force_authenticate(activity_user)
    contact = create_contact(api_client)
    created = api_client.post(
        reverse("contact-activity-list"),
        {"contact": contact["id"], "kind": "note", "subject": "Notiz", "body": "Alt"},
        format="json",
    ).data
    detail = reverse("contact-activity-detail", args=[created["id"]])

    updated = api_client.patch(detail, {"body": "Neu", "version": 1}, format="json")
    conflict = api_client.patch(detail, {"body": "Veraltet", "version": 1}, format="json")

    assert updated.status_code == 200
    assert updated.data["body"] == "Neu"
    assert updated.data["version"] == 2
    assert conflict.status_code == 409
    assert conflict.data["error"]["code"] == "version_conflict"


@pytest.mark.django_db
def test_only_admin_can_archive_activity(api_client, activity_user, activity_admin):
    api_client.force_authenticate(activity_user)
    contact = create_contact(api_client)
    created = api_client.post(
        reverse("contact-activity-list"),
        {"contact": contact["id"], "kind": "email", "subject": "Angebot gesendet"},
        format="json",
    ).data
    archive_url = reverse("contact-activity-archive", args=[created["id"]])

    assert api_client.post(archive_url).status_code == 403
    api_client.force_authenticate(activity_admin)
    archived = api_client.post(archive_url)
    active_timeline = api_client.get(reverse("contact-activity-list"), {"contact": contact["id"]})
    archived_timeline = api_client.get(
        reverse("contact-activity-list"), {"contact": contact["id"], "archived": "true"}
    )
    rejected_update = api_client.patch(
        reverse("contact-activity-detail", args=[created["id"]]),
        {"subject": "Nachträglich geändert", "version": 2},
        format="json",
    )

    assert archived.status_code == 200
    assert archived.data["archived_at"] is not None
    assert active_timeline.data["count"] == 0
    assert archived_timeline.data["count"] == 1
    assert rejected_update.status_code == 400
    assert ContactActivity.objects.get(pk=created["id"]).version == 2


@pytest.mark.django_db
def test_activity_cannot_be_created_for_archived_contact(api_client, activity_user, activity_admin):
    api_client.force_authenticate(activity_user)
    contact = create_contact(api_client)
    api_client.force_authenticate(activity_admin)
    api_client.post(reverse("contact-archive", args=[contact["id"]]))

    response = api_client.post(
        reverse("contact-activity-list"),
        {"contact": contact["id"], "kind": "meeting", "subject": "Zu spät"},
        format="json",
    )

    assert response.status_code == 400
    assert "contact" in response.data["error"]["fields"]
