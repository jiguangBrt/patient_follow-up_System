"""Doctor-scoped patient workspace, with confirmed records grouped by visit day."""

from datetime import UTC
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from patient_follow_up_system.auth import require_roles
from patient_follow_up_system.clinical import document_info, fields_for
from patient_follow_up_system.clinical_ocr import FIELD_LABELS
from patient_follow_up_system.database import get_db
from patient_follow_up_system.models import (
    ClinicalDocument,
    Encounter,
    PatientDocument,
    PatientIntakeLink,
    PatientIntakeSubmission,
    PatientNoticeVersion,
    User,
    UserRole,
)
from patient_follow_up_system.permissions import patient_permissions, require_patient
from patient_follow_up_system.portal_models import PortalConsent, PortalProfile
from patient_follow_up_system.visit_dates import suggest_visit_date

router = APIRouter()


@router.get("/patients/{patient_id}/workspace")
def patient_workspace(
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    doctor: Annotated[User, Depends(require_roles(UserRole.DOCTOR, UserRole.STUDENT))],
):
    patient = require_patient(db, patient_id, doctor)
    owner_id = patient.responsible_doctor_id
    submissions = list(
        db.scalars(
            select(PatientIntakeSubmission)
            .join(
                PatientIntakeLink,
                PatientIntakeSubmission.intake_link_id == PatientIntakeLink.id,
            )
            .where(
                PatientIntakeLink.created_by_doctor_id == owner_id,
                or_(
                    PatientIntakeLink.patient_id == patient_id,
                    PatientIntakeSubmission.created_patient_id == patient_id,
                ),
            )
            .order_by(PatientIntakeSubmission.id.desc())
        )
    )
    documents = list(
        db.scalars(
            select(PatientDocument)
            .where(PatientDocument.patient_id == patient_id)
            .order_by(PatientDocument.id.desc())
        )
    )
    clinical = list(
        db.scalars(
            select(ClinicalDocument)
            .where(
                ClinicalDocument.owner_doctor_id == owner_id,
                or_(
                    ClinicalDocument.patient_id == patient_id,
                    (ClinicalDocument.source_kind == "intake")
                    & ClinicalDocument.source_id.in_([s.id for s in submissions]),
                    (ClinicalDocument.source_kind == "patient")
                    & ClinicalDocument.source_id.in_([d.id for d in documents]),
                ),
            )
            .order_by(ClinicalDocument.id.desc())
        )
    )
    groups, unfiled = {}, []
    imported = {(d.source_kind, d.source_id) for d in clinical}
    filed = {(d.source_kind, d.source_id) for d in clinical if d.status == "filed"}

    def add(day, item):
        key = day.isoformat() if day else ""
        groups.setdefault(key, []).append(item)

    for doc in clinical:
        info = document_info(db, doc, False)
        item = {"kind": "clinical", **info}
        if doc.status == "filed":
            fields = fields_for(db, doc.id)
            item["fields"] = [
                {"label": FIELD_LABELS[f.key], "value": f.confirmed_value}
                for f in fields
                if f.review_status != "pending"
            ]
            add(doc.visit_date or suggest_visit_date(fields, confirmed_only=True), item)
        else:
            item["candidate_date"] = doc.visit_date or info["suggested_visit_date"]
            unfiled.append(item)
    for doc in documents:
        item = {
            "kind": "patient",
            "id": doc.id,
            "original_name": doc.original_name,
            "status": doc.review_status,
            "summary": doc.doctor_summary,
            "label": doc.confirmed_label or doc.display_label,
        }
        source = ("patient", doc.id)
        if doc.review_status == "approved" and source not in filed:
            add(doc.confirmed_event_date, item)
        elif source not in imported:
            unfiled.append(item)
    for row in submissions:
        if row.document_storage_name and ("intake", row.id) not in imported:
            unfiled.append(
                {
                    "kind": "intake",
                    "id": row.id,
                    "original_name": row.document_name,
                    "status": row.status,
                    "candidate_date": None,
                }
            )
    for row in db.scalars(
        select(Encounter).where(
            Encounter.patient_id == patient_id
        )
    ):
        when = (
            row.occurred_at.replace(tzinfo=UTC)
            if row.occurred_at.tzinfo is None
            else row.occurred_at
        )
        add(
            when.astimezone(ZoneInfo("Asia/Shanghai")).date(),
            {"kind": "encounter", "id": row.id, "label": row.display_label},
        )
    latest = submissions[0] if submissions else None
    legacy_profile = {
        "sex": latest.sex,
        "date_of_birth": latest.date_of_birth,
        "operator_relationship": latest.operator_relationship,
        "status": latest.status,
        "notice_version": latest.notice_version,
    } if latest else None
    profile = legacy_profile
    portal_profile = db.get(PortalProfile, patient_id)
    if portal_profile:
        consent = db.scalar(
            select(PortalConsent).where(PortalConsent.patient_id == patient_id)
            .order_by(PortalConsent.id.desc())
        )
        notice = db.get(PatientNoticeVersion, consent.notice_version_id) if consent else None
        profile = {
            "sex": portal_profile.sex,
            "date_of_birth": portal_profile.date_of_birth,
            "phone": portal_profile.phone,
            "operator_relationship": portal_profile.operator_relationship,
            "extra": portal_profile.extra,
            "status": "enrolled",
            "source": "portal",
            "notice_version": notice.version if notice else None,
        }
    return {
        "permissions": patient_permissions(db, patient_id, doctor),
        "profile": profile,
        "legacy_profile": legacy_profile,
        "visits": [
            {"date": day or None, "records": records}
            for day, records in sorted(groups.items(), reverse=True)
        ],
        "unfiled": unfiled,
    }
