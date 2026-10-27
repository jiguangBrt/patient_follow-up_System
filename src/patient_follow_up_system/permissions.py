"""Patient scopes shared by list, file and mutation endpoints. Never trust UI filtering."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import false, func, select
from sqlalchemy.orm import Session

from patient_follow_up_system.models import (
    Patient,
    PatientGrant,
    PatientIntakeLink,
    PatientIntakeSubmission,
    User,
    UserRole,
)


def patient_scope(user: User, operation: str = "view"):
    if user.role == UserRole.DOCTOR:
        return Patient.responsible_doctor_id == user.id
    if user.role == UserRole.PATIENT and operation == "view":
        return Patient.patient_user_id == user.id
    if user.role != UserRole.STUDENT or operation not in ("view", "edit", "review"):
        return false()
    now = datetime.now(UTC).replace(tzinfo=None)
    grants = select(PatientGrant.patient_id).where(
        PatientGrant.student_id == user.id,
        PatientGrant.granted_by_id == user.mentor_doctor_id,
        PatientGrant.revoked_at.is_(None),
        PatientGrant.starts_at <= now,
        PatientGrant.ends_at > now,
    )
    if operation == "edit":
        grants = grants.where(PatientGrant.can_edit.is_(True))
    elif operation == "review":
        grants = grants.where(PatientGrant.can_review.is_(True))
    return (
        Patient.id.in_(grants)
        & (Patient.responsible_doctor_id == user.mentor_doctor_id)
        & select(User.id)
        .where(
            User.id == user.mentor_doctor_id,
            User.role == UserRole.DOCTOR,
            User.is_active.is_(True),
        )
        .exists()
    )


def require_patient(
    db: Session, patient_id: int, user: User, operation: str = "view"
) -> Patient:
    patient = db.scalar(
        select(Patient).where(Patient.id == patient_id, patient_scope(user, operation))
    )
    if patient is None:
        raise HTTPException(404, "患者不存在或没有相应操作权限，授权可能已到期或撤销。")
    return patient


def patient_permissions(db: Session, patient_id: int, user: User) -> list[str]:
    return [
        action
        for action in ("view", "edit", "review")
        if db.scalar(
            select(Patient.id).where(
                Patient.id == patient_id, patient_scope(user, action)
            )
        )
        is not None
    ]


def intake_scope(user: User, operation: str = "view"):
    if user.role == UserRole.DOCTOR:
        return PatientIntakeLink.created_by_doctor_id == user.id
    if user.role != UserRole.STUDENT:
        return false()
    return (
        PatientIntakeLink.created_by_doctor_id == user.mentor_doctor_id
    ) & func.coalesce(
        PatientIntakeSubmission.created_patient_id, PatientIntakeLink.patient_id
    ).in_(select(Patient.id).where(patient_scope(user, operation)))
