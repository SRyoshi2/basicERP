import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.crm.models import Contact, ContactImportBatch


@pytest.fixture
def import_user():
    return get_user_model().objects.create_user(
        username="import-user",
        email="import-user@example.test",
        password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


def csv_upload(content, name="kontakte.csv"):
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


@pytest.mark.django_db
def test_preview_accepts_german_semicolon_csv_and_normalizes_rows(api_client, import_user):
    api_client.force_authenticate(import_user)
    content = (
        "Typ;Firmenname;Vorname;Nachname;E-Mail;Telefon;Straße;PLZ;Ort;Land\n"
        "Firma;Nordlicht GmbH;;;kontakt@nordlicht.example;+49 40 1;Hafenstraße 1;20457;Hamburg;de\n"
        "Person;;Ada;Lovelace;ada@example.test;;;;;\n"
    )

    response = api_client.post(
        reverse("contact-import-preview"), {"file": csv_upload(content)}, format="multipart"
    )

    assert response.status_code == 200
    assert response.data["status"] == "preview"
    assert response.data["total_count"] == 2
    assert response.data["valid_count"] == 2
    assert response.data["error_count"] == 0
    assert response.data["rows"][0]["data"]["kind"] == "organization"
    assert response.data["rows"][0]["data"]["addresses"][0]["country_code"] == "DE"


@pytest.mark.django_db
def test_preview_reports_row_errors_and_apply_is_blocked(api_client, import_user):
    api_client.force_authenticate(import_user)
    content = "Typ;Firmenname;Vorname;Nachname;E-Mail;Straße;PLZ;Ort\nFirma;;;;ungueltig;Nur Straße;;\n"
    preview = api_client.post(
        reverse("contact-import-preview"), {"file": csv_upload(content)}, format="multipart"
    )

    apply_response = api_client.post(
        reverse("contact-import-apply", args=[preview.data["id"]]), {}, format="json"
    )

    assert preview.status_code == 200
    assert preview.data["valid_count"] == 0
    assert preview.data["error_count"] == 1
    assert set(preview.data["rows"][0]["errors"]) == {"company_name", "email", "address"}
    assert apply_response.status_code == 400
    assert Contact.objects.count() == 0


@pytest.mark.django_db
def test_same_file_reuses_preview_and_apply_is_idempotent(api_client, import_user):
    api_client.force_authenticate(import_user)
    content = (
        "kind,company_name,first_name,last_name,email\n"
        "organization,Acme GmbH,,,office@acme.example\n"
        "person,,Grace,Hopper,grace@example.test\n"
    )
    first_preview = api_client.post(
        reverse("contact-import-preview"), {"file": csv_upload(content)}, format="multipart"
    )
    second_preview = api_client.post(
        reverse("contact-import-preview"), {"file": csv_upload(content, "kopie.csv")}, format="multipart"
    )

    first_apply = api_client.post(
        reverse("contact-import-apply", args=[first_preview.data["id"]]), {}, format="json"
    )
    second_apply = api_client.post(
        reverse("contact-import-apply", args=[first_preview.data["id"]]), {}, format="json"
    )

    assert first_preview.data["id"] == second_preview.data["id"]
    assert ContactImportBatch.objects.count() == 1
    assert first_apply.status_code == 200
    assert first_apply.data["status"] == "completed"
    assert first_apply.data["created_count"] == 2
    assert second_apply.data["created_count"] == 2
    assert Contact.objects.count() == 2
    assert list(Contact.objects.values_list("customer_number", flat=True)) == ["K-01001", "K-01002"]


@pytest.mark.django_db
def test_preview_rejects_missing_kind_header_and_non_utf8(api_client, import_user):
    api_client.force_authenticate(import_user)
    missing_header = api_client.post(
        reverse("contact-import-preview"),
        {"file": csv_upload("Firmenname;E-Mail\nAcme;office@acme.example\n")},
        format="multipart",
    )
    invalid_encoding = api_client.post(
        reverse("contact-import-preview"),
        {"file": SimpleUploadedFile("latin1.csv", b"Typ;Firmenname\nFirma;M\xfc\n")},
        format="multipart",
    )

    assert missing_header.status_code == 400
    assert invalid_encoding.status_code == 400
