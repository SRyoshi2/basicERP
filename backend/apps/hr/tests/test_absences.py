from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.hr.models import AbsenceRequest, AbsenceRequestAuditEvent, LeaveEntitlement


@pytest.fixture
def hr_employee():
    return get_user_model().objects.create_user(
        username="hr-employee", email="hr-employee@example.test", password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def other_hr_employee():
    return get_user_model().objects.create_user(
        username="other-hr-employee", email="other-hr@example.test", password="test-password",
        role=get_user_model().Role.EMPLOYEE,
    )


@pytest.fixture
def hr_admin():
    return get_user_model().objects.create_user(
        username="hr-admin", email="hr-admin@example.test", password="test-password",
        role=get_user_model().Role.ADMIN,
    )


def absence_payload(**overrides):
    return {
        "kind": "vacation", "start_date": "2026-11-02", "end_date": "2026-11-06",
        "note": "Herbsturlaub", **overrides,
    }


@pytest.mark.django_db
def test_employee_creates_own_absence_with_working_days_and_audit(api_client, hr_employee):
    api_client.force_authenticate(hr_employee)
    response = api_client.post(reverse("absence-list"), absence_payload(), format="json")

    assert response.status_code == 201
    assert response.data["employee"] == hr_employee.id
    assert response.data["working_days"] == "5.00"
    assert response.data["status"] == "requested"
    event = AbsenceRequestAuditEvent.objects.get(absence_request_id=response.data["id"])
    assert event.action == "created"
    assert event.actor == hr_employee


@pytest.mark.django_db
def test_employee_only_sees_own_requests_and_admin_sees_all(
    api_client, hr_employee, other_hr_employee, hr_admin
):
    absence = AbsenceRequest.objects.create(
        employee=hr_employee, kind="sickness", start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 3),
    )
    detail = reverse("absence-detail", args=[absence.id])

    api_client.force_authenticate(other_hr_employee)
    assert api_client.get(detail).status_code == 404
    assert api_client.get(reverse("absence-list")).data["count"] == 0

    api_client.force_authenticate(hr_admin)
    assert api_client.get(reverse("absence-list"), {"employee": hr_employee.id}).data[
        "count"
    ] == 1


@pytest.mark.django_db
def test_absence_validation_rejects_overlap_weekend_and_cross_year_vacation(
    api_client, hr_employee
):
    api_client.force_authenticate(hr_employee)
    first = api_client.post(reverse("absence-list"), absence_payload(), format="json")
    overlap = api_client.post(
        reverse("absence-list"),
        absence_payload(start_date="2026-11-05", end_date="2026-11-09"), format="json",
    )
    weekend = api_client.post(
        reverse("absence-list"),
        absence_payload(start_date="2026-11-07", end_date="2026-11-08"), format="json",
    )
    cross_year = api_client.post(
        reverse("absence-list"),
        absence_payload(start_date="2026-12-31", end_date="2027-01-04"), format="json",
    )

    assert first.status_code == 201
    assert overlap.status_code == 400
    assert weekend.status_code == 400
    assert cross_year.status_code == 400


@pytest.mark.django_db
def test_admin_sets_entitlement_approves_vacation_and_balance_updates(
    api_client, hr_employee, hr_admin
):
    api_client.force_authenticate(hr_admin)
    entitlement = api_client.post(
        reverse("leave-entitlements"),
        {"employee": hr_employee.id, "year": 2026, "entitlement_days": "25.00", "carryover_days": "2.00"},
        format="json",
    )
    assert entitlement.status_code == 201

    api_client.force_authenticate(hr_employee)
    created = api_client.post(reverse("absence-list"), absence_payload(), format="json").data
    before = api_client.get(reverse("leave-balance"), {"year": 2026})
    assert before.data["pending_days"] == "5.00"
    assert before.data["remaining_days"] == "27.00"

    forbidden = api_client.post(
        reverse("absence-review", args=[created["id"]]), {"decision": "approved"}, format="json"
    )
    assert forbidden.status_code == 403

    api_client.force_authenticate(hr_admin)
    approved = api_client.post(
        reverse("absence-review", args=[created["id"]]),
        {"decision": "approved", "decision_note": "Genehmigt"}, format="json",
    )
    assert approved.status_code == 200
    assert approved.data["status"] == "approved"

    api_client.force_authenticate(hr_employee)
    after = api_client.get(reverse("leave-balance"), {"year": 2026})
    assert after.data["approved_days"] == "5.00"
    assert after.data["pending_days"] == "0.00"
    assert after.data["remaining_days"] == "22.00"


@pytest.mark.django_db
def test_sickness_does_not_consume_leave_and_insufficient_leave_blocks_approval(
    api_client, hr_employee, hr_admin
):
    LeaveEntitlement.objects.create(
        employee=hr_employee, year=2026, entitlement_days="2.00", updated_by=hr_admin
    )
    api_client.force_authenticate(hr_employee)
    sickness = api_client.post(
        reverse("absence-list"), absence_payload(kind="sickness"), format="json"
    ).data
    vacation = api_client.post(
        reverse("absence-list"),
        absence_payload(start_date="2026-11-16", end_date="2026-11-20"), format="json",
    ).data

    api_client.force_authenticate(hr_admin)
    assert api_client.post(
        reverse("absence-review", args=[sickness["id"]]), {"decision": "approved"}, format="json"
    ).status_code == 200
    rejected = api_client.post(
        reverse("absence-review", args=[vacation["id"]]), {"decision": "approved"}, format="json"
    )
    assert rejected.status_code == 400
    assert AbsenceRequest.objects.get(pk=vacation["id"]).status == "requested"

    balance = api_client.get(
        reverse("leave-balance"), {"year": 2026, "employee": hr_employee.id}
    )
    assert balance.data["approved_days"] == "0.00"
    assert balance.data["remaining_days"] == "2.00"


@pytest.mark.django_db
def test_requested_absence_supports_versioned_update_and_cancel(api_client, hr_employee):
    api_client.force_authenticate(hr_employee)
    created = api_client.post(reverse("absence-list"), absence_payload(), format="json").data
    detail = reverse("absence-detail", args=[created["id"]])

    missing_version = api_client.patch(detail, {"note": "Ohne Version"}, format="json")
    updated = api_client.patch(
        detail, {"note": "Mit Version", "version": 1}, format="json"
    )
    conflict = api_client.patch(detail, {"note": "Alt", "version": 1}, format="json")
    cancelled = api_client.post(reverse("absence-cancel", args=[created["id"]]))

    assert missing_version.status_code == 400
    assert updated.status_code == 200
    assert updated.data["version"] == 2
    assert conflict.status_code == 409
    assert cancelled.status_code == 200
    assert cancelled.data["status"] == "cancelled"


@pytest.mark.django_db
def test_entitlement_is_admin_only_and_version_protected(api_client, hr_employee, hr_admin):
    payload = {
        "employee": hr_employee.id, "year": 2026,
        "entitlement_days": "30.00", "carryover_days": "0.00",
    }
    api_client.force_authenticate(hr_employee)
    assert api_client.post(reverse("leave-entitlements"), payload, format="json").status_code == 403

    api_client.force_authenticate(hr_admin)
    created = api_client.post(reverse("leave-entitlements"), payload, format="json")
    stale = api_client.post(
        reverse("leave-entitlements"), {**payload, "entitlement_days": "28.00"}, format="json"
    )
    updated = api_client.post(
        reverse("leave-entitlements"),
        {**payload, "entitlement_days": "28.00", "version": created.data["version"]},
        format="json",
    )

    assert created.status_code == 201
    assert stale.status_code == 409
    assert updated.status_code == 200
    assert updated.data["entitlement_days"] == "28.00"
