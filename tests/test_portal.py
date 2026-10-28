"""Public QR never identifies an existing patient; each browser has a private credential."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import func, select

from patient_follow_up_system.models import Patient, PatientDocument, PatientIntakeSubmission, User
from patient_follow_up_system.portal import now_utc
from patient_follow_up_system.portal_models import PortalAccess, PortalConsent, PortalProfile
import pytest
import test_invitations


@pytest.fixture
def portal_app(tmp_path, monkeypatch):
    yield from test_invitations.invitation_app.__wrapped__(tmp_path, monkeypatch)


def registration(client, identities, token, key="a" * 40, name="虚构患者甲"):
    return client.post("/portal/register", json={"intake_token": token, "registration_key": key, "display_name": name, "sex": "女", "date_of_birth": "1980-01-01", "phone": "13800000000", "operator_relationship": "本人", "notice_version_id": identities["notice"].id, "consent_given": True})


def enroll(client, identities, key="a" * 40):
    link = client.get("/doctor/enrollment-link").json()
    response = registration(client, identities, link["intake_token"], key)
    assert response.status_code == 201, response.text
    data = response.json()
    return link, data, {"Authorization": "Bearer " + data["access_token"]}


def test_public_qr_stable_auto_enrollment_and_no_patient_disclosure(portal_app):
    client, sessions, ids, current = portal_app
    link, data, headers = enroll(client, ids)
    assert client.get("/doctor/enrollment-link").json() == link
    assert client.post("/portal/entry", json={"intake_token": link["intake_token"]}).json() == {"doctor_name": ids["doctor"].display_name, "doctor_id": ids["doctor"].id, "kind": "public", "locked_name": None, "target_binding": None}
    assert client.get("/portal/me").status_code == 401
    assert client.get("/portal/me", headers={"Authorization": "Bearer " + link["intake_token"]}).status_code == 401
    assert client.get("/portal/me", headers=headers).json()["patient"]["id"] == data["patient"]["id"]
    assert registration(client, ids, link["intake_token"]).json()["access_token"] == data["access_token"]
    assert client.get("/portal/me", headers=headers).headers["cache-control"] == "no-store"
    workspace = client.get(f"/patients/{data['patient']['id']}/workspace").json()
    assert workspace["profile"]["sex"] == "女"
    assert workspace["profile"]["date_of_birth"] == "1980-01-01"
    assert workspace["profile"]["phone"] == "13800000000"
    assert workspace["profile"]["status"] == "enrolled"
    assert workspace["profile"]["source"] == "portal"
    assert workspace["profile"]["notice_version"] == ids["notice"].version
    with sessions() as db:
        patient = db.get(Patient, data["patient"]["id"])
        assert patient.responsible_doctor_id == ids["doctor"].id
        assert patient.patient_user_id is not None
        assert db.scalar(select(func.count()).select_from(PortalConsent)) == 1
        assert db.scalar(select(func.count()).select_from(PatientIntakeSubmission)) == 0
    another = registration(client, ids, link["intake_token"], "b" * 40).json()
    assert another["patient"]["id"] != data["patient"]["id"]  # same name/phone is not authentication
    assert another["access_token"] != data["access_token"]


def test_public_code_rotation_does_not_revoke_enrolled_patients(portal_app):
    client, sessions, ids, current = portal_app
    link, data, headers = enroll(client, ids)
    newer = client.post("/doctor/enrollment-link/rotate").json()
    assert newer["intake_token"] != link["intake_token"]
    assert client.post("/portal/entry", json={"intake_token": link["intake_token"]}).status_code == 404
    assert client.get("/portal/me", headers=headers).status_code == 200
    current["value"] = ids["other_doctor"]
    assert client.get("/doctor/enrollment-link").json()["intake_token"] != newer["intake_token"]


def test_registration_consent_and_profile_validation(portal_app):
    client, sessions, ids, current = portal_app
    token = client.get("/doctor/enrollment-link").json()["intake_token"]
    payload = {"intake_token": token, "registration_key": "x" * 40, "display_name": " ", "sex": "女", "date_of_birth": "1980-01-01", "notice_version_id": ids["notice"].id, "consent_given": True}
    assert client.post("/portal/register", json=payload).status_code == 422
    payload.update(display_name="虚构患者")
    payload["consent_given"] = False
    assert client.post("/portal/register", json=payload).status_code == 422
    payload.update(consent_given=True, notice_version_id=9999)
    assert client.post("/portal/register", json=payload).status_code == 409
    payload.update(notice_version_id=ids["notice"].id, date_of_birth="2999-01-01")
    assert client.post("/portal/register", json=payload).status_code == 422
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(PortalAccess)) == 0


def test_dedicated_qr_restores_same_patient_without_reenrollment(portal_app):
    client, sessions, ids, current = portal_app
    link = client.post(f"/patients/{ids['patient'].id}/intake-link").json()
    legacy = client.post("/intake-submissions", json=test_invitations.named_intake_payload(ids, link))
    assert legacy.status_code == 201
    first = registration(client, ids, link["intake_token"], name=ids["patient"].display_name)
    assert first.status_code == 201, first.text
    entry = client.post("/portal/entry", json={"intake_token": link["intake_token"]}).json()
    assert entry["target_binding"] == first.json()["target_binding"]
    assert str(ids["patient"].id) != entry["target_binding"]
    workspace = client.get(f"/patients/{ids['patient'].id}/workspace").json()
    assert workspace["profile"]["status"] == "enrolled"
    assert workspace["legacy_profile"]["status"] == "pending"
    with sessions() as db:
        assert db.get(PatientIntakeSubmission, legacy.json()["id"]).status == "pending"
    second = registration(client, ids, link["intake_token"], "b" * 40, ids["patient"].display_name)
    assert second.status_code == 201
    assert second.json()["patient"]["id"] == first.json()["patient"]["id"] == ids["patient"].id
    headers = {"Authorization": "Bearer " + second.json()["access_token"]}
    assert client.post(f"/intake-links/{link['id']}/revoke").status_code == 200
    assert client.get("/portal/me", headers=headers).status_code == 401


def test_profile_updates_stay_private_and_refresh_without_approval(portal_app):
    client, sessions, ids, current = portal_app
    link, data, headers = enroll(client, ids)
    body = {"display_name": "虚构新姓名", "sex": "男", "date_of_birth": "1981-01-01", "phone": "13900000000", "extra": {"occupation": "虚构职业"}}
    response = client.put("/portal/me", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["profile"]["extra"] == body["extra"]
    assert client.get("/portal/me", headers=headers).json()["patient"]["display_name"] == body["display_name"]
    assert client.put("/portal/me", json=body).status_code == 401
    with sessions() as db:
        assert db.get(PortalProfile, data["patient"]["id"]).sex == "男"


def test_private_token_expiry_logout_and_account_deactivation(portal_app):
    client, sessions, ids, current = portal_app
    link, data, headers = enroll(client, ids)
    with sessions() as db:
        doctor = db.get(User, ids["doctor"].id)
        doctor.is_active = False
        db.commit()
    assert client.get("/portal/me", headers=headers).status_code == 403
    assert registration(client, ids, link["intake_token"], "b" * 40).status_code == 410
    with sessions() as db:
        db.get(User, ids["doctor"].id).is_active = True
        access = db.scalar(select(PortalAccess))
        access.expires_at = now_utc() - timedelta(seconds=1)
        db.commit()
    assert client.get("/portal/me", headers=headers).status_code == 401
    assert registration(client, ids, link["intake_token"]).status_code == 409
    link, data, headers = enroll(client, ids, "c" * 40)
    assert client.post("/portal/logout", headers=headers).json() == {"revoked": True}
    assert client.get("/portal/me", headers=headers).status_code == 401


def test_uploads_are_repeatable_idempotent_private_and_pending_for_clinical_review(portal_app):
    client, sessions, ids, current = portal_app
    link, data, headers = enroll(client, ids)
    body = {"event_date": "2026-01-01", "display_label": "门诊病历", "notice_version_id": ids["notice"].id, "consent_given": True, "submission_key": "u" * 32, "document_name": "fictional.png", "document_mime_type": "image/png", "document_base64": base64.b64encode(b"\x89PNG\r\n\x1a\nfake-for-signature-test").decode()}
    result = client.post("/portal/documents", headers=headers, json=body)
    assert result.status_code == 201, result.text
    document = result.json()
    assert document["review_status"] == "pending"
    assert client.post("/portal/documents", headers=headers, json=body).json()["id"] == document["id"]
    body["submission_key"] = "v" * 32
    assert client.post("/portal/documents", headers=headers, json=body).status_code == 201
    assert len(client.get("/portal/documents", headers=headers).json()) == 2
    workspace = client.get(f"/patients/{data['patient']['id']}/workspace").json()
    assert len(workspace["unfiled"]) == 2
    assert {row["kind"] for row in workspace["unfiled"]} == {"patient"}
    assert document["id"] in {row["id"] for row in workspace["unfiled"]}
    assert client.get(f"/portal/documents/{document['id']}/file", headers=headers).content == base64.b64decode(body["document_base64"])
    other = registration(client, ids, link["intake_token"], "b" * 40).json()
    other_headers = {"Authorization": "Bearer " + other["access_token"]}
    assert client.get(f"/portal/documents/{document['id']}/file", headers=other_headers).status_code == 404
    assert client.get("/portal/documents", headers=other_headers).json() == []
    body["submission_key"] = "w" * 32
    body["consent_given"] = False
    assert client.post("/portal/documents", headers=headers, json=body).status_code == 422
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(PatientDocument)) == 2


def test_parallel_registration_retries_create_one_patient(portal_app):
    client, sessions, ids, current = portal_app
    token = client.get("/doctor/enrollment-link").json()["intake_token"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: registration(client, ids, token), range(2)))
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json() == results[1].json()
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(PortalAccess)) == 1
        assert db.scalar(select(func.count()).select_from(PortalProfile)) == 1


def test_parallel_upload_retries_create_one_document(portal_app):
    client, sessions, ids, current = portal_app
    link, data, headers = enroll(client, ids)
    body = {"event_date": "2026-01-01", "display_label": "门诊病历", "notice_version_id": ids["notice"].id, "consent_given": True, "submission_key": "parallel" * 5, "document_name": "fictional.png", "document_mime_type": "image/png", "document_base64": base64.b64encode(b"\x89PNG\r\n\x1a\nfake-for-signature-test").decode()}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post("/portal/documents", headers=headers, json=body), range(2)))
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json()["id"] == results[1].json()["id"]
    with sessions() as db:
        assert db.scalar(select(func.count()).select_from(PatientDocument)) == 1
