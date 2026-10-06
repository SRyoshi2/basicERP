import base64

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.core.models import CompanyProfile


@pytest.fixture
def admin_user():
    return get_user_model().objects.create_user(
        username="owner",
        email="owner@example.test",
        password="secret-test-password",
        role=get_user_model().Role.ADMIN,
    )


@pytest.fixture
def employee_user():
    return get_user_model().objects.create_user(
        username="employee",
        email="employee@example.test",
        password="secret-test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.mark.django_db
def test_employee_can_read_but_not_change_company(api_client, employee_user):
    api_client.force_authenticate(employee_user)

    response = api_client.get(reverse("company-profile"))
    assert response.status_code == 200
    assert response.data["country_code"] == "DE"

    response = api_client.patch(reverse("company-profile"), {"name": "Nicht erlaubt"}, format="json")
    assert response.status_code == 403
    assert CompanyProfile.objects.get().name == ""


@pytest.mark.django_db
def test_admin_can_change_company(api_client, admin_user):
    api_client.force_authenticate(admin_user)

    response = api_client.patch(
        reverse("company-profile"),
        {"name": "Musterbüro", "country_code": "de", "website": "https://example.test"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["name"] == "Musterbüro"
    assert response.data["country_code"] == "DE"
    company = CompanyProfile.objects.get(pk=1)
    assert company.updated_by == admin_user


@pytest.mark.django_db
def test_admin_can_upload_raster_logo(api_client, admin_user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    api_client.force_authenticate(admin_user)
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )

    response = api_client.patch(
        reverse("company-profile"),
        {"logo": SimpleUploadedFile("logo.png", png, content_type="image/png")},
        format="multipart",
    )

    assert response.status_code == 200
    assert response.data["logo_url"].startswith("/media/company/logos/")


@pytest.mark.django_db
def test_svg_logo_is_rejected(api_client, admin_user):
    api_client.force_authenticate(admin_user)
    svg = SimpleUploadedFile(
        "logo.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        content_type="image/svg+xml",
    )

    response = api_client.patch(reverse("company-profile"), {"logo": svg}, format="multipart")

    assert response.status_code == 400
    assert "logo" in response.data
