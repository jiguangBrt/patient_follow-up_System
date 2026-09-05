from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from patient_follow_up_system.auth import get_current_user
from patient_follow_up_system.database import Base, get_db
from patient_follow_up_system.invitations import (
    digest_invitation_token,
    generate_verification_code,
)
from patient_follow_up_system.main import app
from patient_follow_up_system.models import (
    Encounter,
    Patient,
    PatientIntakeLink,
    PatientIntakeSubmission,
    PatientInvitation,
    User,
    UserRole,
)


@pytest.fixture
def invitation_app(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    with testing_session() as session:
        doctor = User(
            username="test_doctor",
            display_name="虚构测试医生",
            password_hash="not-used",
            role=UserRole.DOCTOR,
        )
        other_doctor = User(
            username="other_doctor",
            display_name="虚构其他医生",
            password_hash="not-used",
            role=UserRole.DOCTOR,
        )
        patient_user = User(
            username="test_patient",
            display_name="虚构测试患者账号",
            password_hash="not-used",
            role=UserRole.PATIENT,
        )
        other_patient_user = User(
            username="other_patient",
            display_name="虚构其他患者账号",
            password_hash="not-used",
            role=UserRole.PATIENT,
        )
        session.add_all(
            [doctor, other_doctor, patient_user, other_patient_user]
        )
        session.flush()
        patient = Patient(
            patient_code="TEST-PATIENT-001",
            display_name="虚构测试患者甲",
            responsible_doctor_id=doctor.id,
        )
        other_patient = Patient(
            patient_code="TEST-PATIENT-002",
            display_name="虚构测试患者乙",
            responsible_doctor_id=other_doctor.id,
            patient_user_id=other_patient_user.id,
        )
        session.add_all([patient, other_patient])
        session.flush()
        encounter = Encounter(
            encounter_code="TEST-ENCOUNTER-001",
            patient_id=patient.id,
            doctor_id=doctor.id,
            occurred_at=datetime(2026, 9, 3),
            display_label="模拟测试就诊",
        )
        session.add(encounter)
        session.commit()
        identities = {
            "doctor": doctor,
            "other_doctor": other_doctor,
            "patient_user": patient_user,
            "other_patient_user": other_patient_user,
            "patient": patient,
            "other_patient": other_patient,
            "encounter": encounter,
        }

    current_user = {"value": identities["doctor"]}

    def override_db() -> Generator[Session, None, None]:
        with testing_session() as session:
            yield session

    def override_user() -> User:
        return current_user["value"]

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        with TestClient(app) as client:
            yield client, testing_session, identities, current_user
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def create_invitation(client, patient_id: int, encounter_id: int | None = None):
    payload = {"expires_in_minutes": 60, "max_uses": 1}
    if encounter_id is not None:
        payload["encounter_id"] = encounter_id
    response = client.post(f"/patients/{patient_id}/invitations", json=payload)
    assert response.status_code == 201
    return response.json()


def test_verification_code_is_six_digits_for_mobile_entry() -> None:
    codes = {generate_verification_code() for _ in range(20)}
    assert len(codes) > 1
    assert all(
        len(code) == 6 and code.isascii() and code.isdigit()
        for code in codes
    )


def test_create_status_bind_and_repeat_are_safe(invitation_app) -> None:
    client, session_factory, identities, current_user = invitation_app
    result = create_invitation(
        client,
        identities["patient"].id,
        identities["encounter"].id,
    )
    assert len(result["verification_code"]) == 6
    assert result["verification_code"].isdigit()
    assert "/invite#token=" in result["invitation_url"]
    assert "<svg" in result["qr_svg"]

    with session_factory() as session:
        invitation = session.scalar(select(PatientInvitation))
        assert invitation is not None
        assert invitation.token_digest == digest_invitation_token(
            result["invitation_token"]
        )
        assert invitation.token_digest != result["invitation_token"]
        assert invitation.verification_code_hash != result["verification_code"]

    status_response = client.post(
        "/invitations/status",
        json={"invitation_token": result["invitation_token"]},
    )
    assert status_response.json() == {"state": "available"}
    assert client.post(
        "/invitations/status",
        json={"invitation_token": "x" * 20},
    ).json() == {
        "state": "unavailable"
    }

    current_user["value"] = identities["patient_user"]
    bind_url = "/invitations/bind"
    bind_response = client.post(
        bind_url,
        json={
            "invitation_token": result["invitation_token"],
            "verification_code": result["verification_code"],
        },
    )
    assert bind_response.status_code == 200
    assert bind_response.json() == {"bound": True, "already_bound": False}
    repeat_response = client.post(
        bind_url,
        json={
            "invitation_token": result["invitation_token"],
            "verification_code": result["verification_code"],
        },
    )
    assert repeat_response.status_code == 200
    assert repeat_response.json() == {"bound": True, "already_bound": True}
    assert client.post(
        "/invitations/status",
        json={"invitation_token": result["invitation_token"]},
    ).json() == {"state": "exhausted"}

    with session_factory() as session:
        patient = session.get(Patient, identities["patient"].id)
        invitation = session.scalar(select(PatientInvitation))
        assert patient.patient_user_id == identities["patient_user"].id
        assert invitation.used_count == 1


def test_scope_revoke_lock_and_binding_conflict(invitation_app) -> None:
    client, session_factory, identities, current_user = invitation_app
    current_user["value"] = identities["other_doctor"]
    denied = client.post(
        f"/patients/{identities['patient'].id}/invitations",
        json={},
    )
    assert denied.status_code == 404

    current_user["value"] = identities["doctor"]
    revoked = create_invitation(client, identities["patient"].id)
    revoke_response = client.post(
        f"/invitations/{revoked['id']}/revoke"
    )
    assert revoke_response.json()["state"] == "revoked"
    assert client.post(
        "/invitations/status",
        json={"invitation_token": revoked["invitation_token"]},
    ).json() == {"state": "revoked"}
    current_user["value"] = identities["patient_user"]
    revoked_bind = client.post(
        "/invitations/bind",
        json={
            "invitation_token": revoked["invitation_token"],
            "verification_code": revoked["verification_code"],
        },
    )
    assert revoked_bind.status_code == 410

    current_user["value"] = identities["doctor"]
    locked = create_invitation(client, identities["patient"].id)
    current_user["value"] = identities["patient_user"]
    for _ in range(5):
        response = client.post(
            "/invitations/bind",
            json={
                "invitation_token": locked["invitation_token"],
                "verification_code": "999999",
            },
        )
        assert response.status_code == 400
    assert client.post(
        "/invitations/status",
        json={"invitation_token": locked["invitation_token"]},
    ).json() == {"state": "locked"}

    conflict = create_invitation_for_other_patient(
        client,
        identities,
        current_user,
    )
    current_user["value"] = identities["patient_user"]
    conflict_response = client.post(
        "/invitations/bind",
        json={
            "invitation_token": conflict["invitation_token"],
            "verification_code": conflict["verification_code"],
        },
    )
    assert conflict_response.status_code == 409


def create_invitation_for_other_patient(client, identities, current_user):
    current_user["value"] = identities["other_doctor"]
    return create_invitation(client, identities["other_patient"].id)


def test_pages_and_api_paths_do_not_put_tokens_in_paths(invitation_app) -> None:
    client, _, _, _ = invitation_app
    doctor_page = client.get("/doctor")
    assert doctor_page.status_code == 200
    assert "新增虚构患者" in doctor_page.text
    assert "基本情况" in doctor_page.text
    assert "新增模拟就诊" in doctor_page.text
    assert client.get("/invite").status_code == 200
    paths = app.openapi()["paths"]
    assert "/invitations/status" in paths
    assert "/invitations/bind" in paths
    assert all("{invitation_token}" not in path for path in paths)


def test_expired_invitation_and_wrong_roles_are_rejected(invitation_app) -> None:
    client, session_factory, identities, current_user = invitation_app
    expired = create_invitation(client, identities["patient"].id)
    with session_factory() as session:
        invitation = session.get(PatientInvitation, expired["id"])
        invitation.expires_at = (
            datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
        )
        session.commit()

    assert client.post(
        "/invitations/status",
        json={"invitation_token": expired["invitation_token"]},
    ).json() == {"state": "expired"}
    current_user["value"] = identities["patient_user"]
    assert client.post(
        "/invitations/bind",
        json={
            "invitation_token": expired["invitation_token"],
            "verification_code": expired["verification_code"],
        },
    ).status_code == 410
    assert client.post(
        f"/patients/{identities['patient'].id}/invitations",
        json={},
    ).status_code == 403

    current_user["value"] = identities["doctor"]
    assert client.post(
        "/invitations/bind",
        json={
            "invitation_token": expired["invitation_token"],
            "verification_code": expired["verification_code"],
        },
    ).status_code == 403


def test_database_rejects_invalid_limits_and_foreign_keys(invitation_app) -> None:
    _, session_factory, identities, _ = invitation_app
    base_values = {
        "verification_code_hash": "not-a-real-hash",
        "patient_id": identities["patient"].id,
        "created_by_doctor_id": identities["doctor"].id,
        "expires_at": datetime.now() + timedelta(hours=1),
    }
    with session_factory() as session:
        session.add(
            PatientInvitation(
                token_digest="a" * 64,
                max_uses=0,
                **base_values,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            PatientInvitation(
                token_digest="b" * 64,
                patient_id=999999,
                verification_code_hash=base_values["verification_code_hash"],
                created_by_doctor_id=base_values["created_by_doctor_id"],
                expires_at=base_values["expires_at"],
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_generic_intake_requires_doctor_review_before_patient_creation(invitation_app) -> None:
    client, session_factory, identities, current_user = invitation_app
    link_response = client.post("/intake-links", json={})
    assert link_response.status_code == 201
    link_data = link_response.json()
    assert "/intake#token=" in link_data["intake_url"]
    with session_factory() as session:
        link = session.scalar(select(PatientIntakeLink))
        assert link.token_digest == digest_invitation_token(link_data["intake_token"])
        assert link.token_digest != link_data["intake_token"]

    submission_response = client.post(
        "/intake-submissions",
        json={
            "intake_token": link_data["intake_token"],
            "submission_key": "anonymous-intake-submission-key-001",
            "display_name": "虚构待审核患者",
            "sex": "未说明",
            "date_of_birth": "1950-01-01",
            "operator_relationship": "家属协助",
            "notice_version": "demo-notice-v1",
            "consent_given": True,
            "document_name": "deidentified-demo.png",
            "document_mime_type": "image/png",
            "document_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
        },
    )
    assert submission_response.status_code == 201
    assert submission_response.json()["status"] == "pending"
    with session_factory() as session:
        assert session.scalar(select(Patient).where(Patient.patient_code == "REVIEWED-001")) is None
        assert session.scalar(select(PatientIntakeSubmission)).status == "pending"

    current_user["value"] = identities["doctor"]
    review_response = client.post(
        f"/intake-submissions/{submission_response.json()['id']}/review",
        json={"action": "approve", "patient_code": "REVIEWED-001"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "approved"
    with session_factory() as session:
        patient = session.scalar(select(Patient).where(Patient.patient_code == "REVIEWED-001"))
        assert patient is not None
        assert patient.patient_user_id is None
        assert patient.responsible_doctor_id == identities["doctor"].id
