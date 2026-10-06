import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_bootstrap_admin_is_idempotent(monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "admin@example.test")

    call_command("bootstrap_admin")
    call_command("bootstrap_admin")

    user_model = get_user_model()
    assert user_model.objects.filter(username="admin").count() == 1
    user = user_model.objects.get(username="admin")
    assert user.check_password("admin")
    assert user.must_change_password is True


@pytest.mark.django_db
def test_admin_must_change_password(api_client, monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "admin@example.test")
    call_command("bootstrap_admin")

    csrf_response = api_client.get(reverse("auth-csrf"))
    assert csrf_response.status_code == 200

    login_response = api_client.post(
        reverse("auth-login"),
        {"identifier": "admin", "password": "admin"},
        format="json",
    )
    assert login_response.status_code == 200
    assert login_response.data["must_change_password"] is True
    assert login_response.data["role"] == "admin"

    change_response = api_client.post(
        reverse("auth-change-password"),
        {"current_password": "admin", "new_password": "Eine-gute-Phrase-2026!"},
        format="json",
    )
    assert change_response.status_code == 200
    assert change_response.data["must_change_password"] is False

    user = get_user_model().objects.get(username="admin")
    assert user.check_password("Eine-gute-Phrase-2026!")


@pytest.mark.django_db
def test_login_requires_csrf_token(monkeypatch):
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "admin")
    monkeypatch.setenv("INITIAL_ADMIN_EMAIL", "admin@example.test")
    call_command("bootstrap_admin")
    client = Client(enforce_csrf_checks=True)

    rejected = client.post(
        reverse("auth-login"),
        {"identifier": "admin", "password": "admin"},
        content_type="application/json",
    )
    assert rejected.status_code == 403
    assert rejected.json() == {
        "error": {
            "code": "csrf_failed",
            "message": "Die Sicherheitsprüfung ist fehlgeschlagen. Bitte lade die Seite neu.",
        }
    }

    csrf_response = client.get(reverse("auth-csrf"))
    token = csrf_response.json()["csrfToken"]
    accepted = client.post(
        reverse("auth-login"),
        {"identifier": "admin", "password": "admin"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert accepted.status_code == 200


@pytest.mark.django_db
def test_invalid_credentials_use_error_envelope(api_client):
    response = api_client.post(
        reverse("auth-login"),
        {"identifier": "unknown", "password": "wrong"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data == {
        "error": {"code": "invalid_credentials", "message": "Anmeldedaten sind ungültig."}
    }
