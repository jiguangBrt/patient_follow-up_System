from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from patient_follow_up_system.auth import get_current_user
from patient_follow_up_system.database import Base, get_db
from patient_follow_up_system.main import app
from patient_follow_up_system.models import User, UserRole


@pytest.fixture
def onboarding_app(tmp_path, monkeypatch):
    monkeypatch.setenv("PATIENT_UPLOAD_DIR", str(tmp_path / "patient_uploads"))
    monkeypatch.setenv("INTAKE_UPLOAD_DIR", str(tmp_path / "intake_uploads"))
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    with testing_session() as session:
        doctor = User(
            username="tour_doctor",
            display_name="虚构测试医生",
            password_hash="not-used",
            role=UserRole.DOCTOR,
        )
        other_doctor = User(
            username="tour_other_doctor",
            display_name="虚构其他医生",
            password_hash="not-used",
            role=UserRole.DOCTOR,
        )
        patient_user = User(
            username="tour_patient",
            display_name="虚构测试患者",
            password_hash="not-used",
            role=UserRole.PATIENT,
        )
        session.add_all([doctor, other_doctor, patient_user])
        session.commit()
        identities = {
            "doctor": doctor,
            "other_doctor": other_doctor,
            "patient_user": patient_user,
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
            yield client, identities, current_user
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_new_doctor_defaults_to_pending(onboarding_app) -> None:
    client, _, _ = onboarding_app
    response = client.get("/onboarding/doctor-tour")
    assert response.status_code == 200
    assert response.json() == {"tour_key": "doctor_workspace", "status": "pending"}


def test_skip_and_complete_are_recorded_and_idempotent(onboarding_app) -> None:
    client, _, _ = onboarding_app
    skipped = client.post("/onboarding/doctor-tour", json={"action": "skip"})
    assert skipped.status_code == 200
    assert skipped.json()["status"] == "skipped"
    assert client.get("/onboarding/doctor-tour").json()["status"] == "skipped"
    again = client.post("/onboarding/doctor-tour", json={"action": "skip"})
    assert again.status_code == 200
    assert again.json()["status"] == "skipped"
    completed = client.post("/onboarding/doctor-tour", json={"action": "complete"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"


def test_state_is_tracked_per_account(onboarding_app) -> None:
    client, _, current_user = onboarding_app
    response = client.post("/onboarding/doctor-tour", json={"action": "complete"})
    assert response.status_code == 200
    current_user["value"] = onboarding_app[1]["other_doctor"]
    assert client.get("/onboarding/doctor-tour").json()["status"] == "pending"


def test_patient_role_cannot_read_or_write(onboarding_app) -> None:
    client, identities, current_user = onboarding_app
    current_user["value"] = identities["patient_user"]
    assert client.get("/onboarding/doctor-tour").status_code == 403
    assert (
        client.post("/onboarding/doctor-tour", json={"action": "skip"}).status_code
        == 403
    )


def test_invalid_action_is_rejected(onboarding_app) -> None:
    client, _, _ = onboarding_app
    assert (
        client.post("/onboarding/doctor-tour", json={"action": "reset"}).status_code
        == 422
    )
