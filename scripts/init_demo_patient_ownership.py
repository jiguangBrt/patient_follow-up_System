import sys
from pathlib import Path

from sqlalchemy import select


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from patient_follow_up_system.database import SessionLocal  # noqa: E402
from patient_follow_up_system.models import Patient, User, UserRole  # noqa: E402


PATIENT_CODE = "DEMO-PATIENT-001"
PATIENT_USERNAME = "demo_patient"
DOCTOR_USERNAME = "demo_doctor"


def required_user(session, username: str, role: UserRole) -> User:
    user = session.scalar(select(User).where(User.username == username))
    if user is None:
        raise RuntimeError(f"Required demo user does not exist: {username}")
    if user.role != role:
        raise RuntimeError(f"Demo user has unexpected role: {username}")
    return user


def main() -> None:
    with SessionLocal() as session:
        patient = session.scalar(
            select(Patient).where(Patient.patient_code == PATIENT_CODE)
        )
        if patient is None:
            raise RuntimeError(f"Required demo patient does not exist: {PATIENT_CODE}")

        patient_user = required_user(session, PATIENT_USERNAME, UserRole.PATIENT)
        doctor_user = required_user(session, DOCTOR_USERNAME, UserRole.DOCTOR)

        if patient.patient_user_id not in (None, patient_user.id):
            raise RuntimeError("Demo patient is already linked to another patient user")
        if patient.responsible_doctor_id not in (None, doctor_user.id):
            raise RuntimeError("Demo patient is already assigned to another doctor")

        changed = (
            patient.patient_user_id != patient_user.id
            or patient.responsible_doctor_id != doctor_user.id
        )
        patient.patient_user_id = patient_user.id
        patient.responsible_doctor_id = doctor_user.id
        session.commit()

        print(f"PATIENT={patient.patient_code},{patient.display_name}")
        print(f"PATIENT_USER={patient_user.username}")
        print(f"RESPONSIBLE_DOCTOR={doctor_user.username}")
        print(f"OWNERSHIP_CREATED={changed}")


if __name__ == "__main__":
    main()
