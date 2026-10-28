"""Mobile self-enrollment. Public QR codes enroll, private bearer tokens read records."""
import hashlib
import hmac
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from patient_follow_up_system.auth import hash_password, require_env, require_roles
from patient_follow_up_system.database import get_db
from patient_follow_up_system.invitations import digest_invitation_token, invitation_qr_svg
from patient_follow_up_system.link_urls import public_base_url
from patient_follow_up_system.models import Patient, PatientDocument, PatientIntakeLink, User, UserRole
from patient_follow_up_system.portal_models import DoctorEnrollmentLink, PortalAccess, PortalConsent, PortalDocumentSubmission, PortalProfile

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
Doctor = Annotated[User, Depends(require_roles(UserRole.DOCTOR))]


def now_utc():
    return datetime.now(UTC).replace(tzinfo=None)


def secret_token(namespace: str, value: str) -> str:
    return hmac.new(require_env("AUTH_SECRET_KEY").encode(), f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()


class EntryRequest(BaseModel):
    intake_token: str = Field(min_length=20, max_length=128)


class ProfileRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    sex: Literal["男", "女", "未说明"]
    date_of_birth: date
    phone: str | None = Field(default=None, max_length=30)
    operator_relationship: Literal["本人", "家属协助"] = "本人"
    extra: dict = Field(default_factory=dict)

    @field_validator("display_name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("请填写姓名。")
        return value.strip()

    @field_validator("date_of_birth")
    @classmethod
    def birth_not_future(cls, value):
        if value > datetime.now(UTC).date():
            raise ValueError("出生日期不能晚于今天。")
        return value

    @field_validator("extra")
    @classmethod
    def bounded_extra(cls, value):
        import json
        if len(json.dumps(value, ensure_ascii=False)) > 12000:
            raise ValueError("基本信息内容过长。")
        return value


class RegisterRequest(ProfileRequest, EntryRequest):
    registration_key: str = Field(min_length=32, max_length=128)
    notice_version_id: int = Field(ge=1)
    consent_given: bool


class DocumentRequest(BaseModel):
    event_date: date
    display_label: str = Field(min_length=1, max_length=100)
    patient_note: str | None = Field(default=None, max_length=500)
    submission_key: str = Field(min_length=20, max_length=128)
    notice_version_id: int = Field(ge=1)
    consent_given: bool
    document_name: str = Field(min_length=1, max_length=255)
    document_mime_type: Literal["image/jpeg", "image/png", "application/pdf"]
    document_base64: str = Field(min_length=4, max_length=11_200_000)


def resolve_entry(db: Session, token: str):
    digest = digest_invitation_token(token)
    enrollment = db.scalar(select(DoctorEnrollmentLink).where(DoctorEnrollmentLink.token_digest == digest))
    link = None if enrollment else db.scalar(select(PatientIntakeLink).where(PatientIntakeLink.token_digest == digest))
    if not enrollment and not link:
        raise HTTPException(404, "建档二维码不可用，请联系医生。")
    if link:
        from patient_follow_up_system.main import intake_link_state
        if intake_link_state(link).value != "available":
            raise HTTPException(410, "建档二维码已失效，请联系医生。")
    doctor_id = enrollment.doctor_id if enrollment else link.created_by_doctor_id
    doctor = db.get(User, doctor_id)
    if not doctor or not doctor.is_active or doctor.role != UserRole.DOCTOR:
        raise HTTPException(410, "医生团队当前不可用。")
    return enrollment, link, doctor


def get_portal_patient(request: Request, db: Db) -> Patient:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(401, "请先完善基本信息或使用本人的访问凭据。")
    access = db.scalar(select(PortalAccess).where(PortalAccess.token_digest == digest_invitation_token(auth[7:])))
    if not access or access.revoked_at or access.expires_at <= now_utc():
        raise HTTPException(401, "患者访问凭据已失效，请联系医生重新获取本人二维码。")
    patient = db.get(Patient, access.patient_id)
    doctor = db.get(User, patient.responsible_doctor_id) if patient else None
    user = db.get(User, patient.patient_user_id) if patient and patient.patient_user_id else None
    if not patient or not doctor or not doctor.is_active or doctor.role != UserRole.DOCTOR or not user or not user.is_active or user.role != UserRole.PATIENT:
        raise HTTPException(403, "患者或医生账号当前不可用。")
    if access.intake_link_id:
        link = db.get(PatientIntakeLink, access.intake_link_id)
        from patient_follow_up_system.main import intake_link_state
        if not link or link.patient_id != patient.id or link.created_by_doctor_id != doctor.id or intake_link_state(link).value != "available":
            raise HTTPException(401, "本人二维码已撤销，请联系医生。")
    return patient


PortalPatient = Annotated[Patient, Depends(get_portal_patient)]


def portal_me(patient: Patient, db: Session):
    profile = db.get(PortalProfile, patient.id)
    doctor = db.get(User, patient.responsible_doctor_id)
    return {
        "patient": {"id": patient.id, "display_name": patient.display_name, "patient_code": patient.patient_code},
        "profile": ({"display_name": patient.display_name, "sex": profile.sex, "date_of_birth": profile.date_of_birth, "phone": profile.phone, "operator_relationship": profile.operator_relationship, "extra": profile.extra} if profile else None),
        "doctor_name": doctor.display_name,
        "target_binding": secret_token("portal-patient-binding", str(patient.id)),
    }


def enrollment_response(link, request):
    token = secret_token("doctor-enrollment", link.nonce)
    url = f"{public_base_url(request)}/intake#token={token}"
    return {"id": link.id, "intake_token": token, "intake_url": url, "qr_svg": invitation_qr_svg(url), "expires_at": None, "state": "available"}


@router.get("/doctor/enrollment-link")
@router.post("/doctor/enrollment-link")
def enrollment_link(request: Request, db: Db, doctor: Doctor):
    # A no-op account write serializes creation without a check-then-insert race.
    db.execute(update(User).where(User.id == doctor.id).values(display_name=User.display_name))
    link = db.scalar(select(DoctorEnrollmentLink).where(DoctorEnrollmentLink.doctor_id == doctor.id))
    if not link:
        nonce = secrets.token_urlsafe(32)
        link = DoctorEnrollmentLink(doctor_id=doctor.id, nonce=nonce, token_digest=digest_invitation_token(secret_token("doctor-enrollment", nonce)))
        db.add(link)
        db.commit()
        db.refresh(link)
    else:
        db.commit()
    return enrollment_response(link, request)


@router.post("/doctor/enrollment-link/rotate")
def rotate_enrollment(request: Request, db: Db, doctor: Doctor):
    db.execute(update(User).where(User.id == doctor.id).values(display_name=User.display_name))
    link = db.scalar(select(DoctorEnrollmentLink).where(DoctorEnrollmentLink.doctor_id == doctor.id))
    nonce = secrets.token_urlsafe(32)
    if not link:
        link = DoctorEnrollmentLink(doctor_id=doctor.id)
        db.add(link)
    link.nonce = nonce
    link.token_digest = digest_invitation_token(secret_token("doctor-enrollment", nonce))
    db.commit()
    db.refresh(link)
    return enrollment_response(link, request)


@router.post("/portal/entry")
def entry(body: EntryRequest, db: Db):
    enrollment, link, doctor = resolve_entry(db, body.intake_token)
    patient = db.get(Patient, link.patient_id) if link and link.patient_id else None
    if patient and patient.responsible_doctor_id != doctor.id:
        raise HTTPException(404, "患者二维码不可用。")
    return {"doctor_name": doctor.display_name, "doctor_id": doctor.id, "kind": "patient" if patient else "public", "locked_name": patient.display_name if patient else None, "target_binding": secret_token("portal-patient-binding", str(patient.id)) if patient else None}


@router.post("/portal/register", status_code=201)
def register(body: RegisterRequest, db: Db):
    from patient_follow_up_system.main import current_patient_notice, generate_record_code
    enrollment, link, doctor = resolve_entry(db, body.intake_token)
    db.execute(update(User).where(User.id == doctor.id).values(display_name=User.display_name))
    # Recheck after obtaining the lock (rotation/deactivation may have won).
    db.expire_all()
    enrollment, link, doctor = resolve_entry(db, body.intake_token)
    registration_digest = digest_invitation_token(body.intake_token + ":" + body.registration_key)
    existing = db.scalar(select(PortalAccess).where(PortalAccess.registration_digest == registration_digest))
    token = secret_token("portal-access", registration_digest)
    if existing:
        if existing.revoked_at or existing.expires_at <= now_utc():
            raise HTTPException(409, "此访问凭据已失效，请重新开始建档。")
        return {"access_token": token, **portal_me(db.get(Patient, existing.patient_id), db)}
    notice = current_patient_notice(db)
    if not body.consent_given:
        raise HTTPException(422, "请阅读并同意患者须知。")
    if not notice or notice.id != body.notice_version_id:
        raise HTTPException(409, "患者须知已更新，请查看最新版本后重试。")
    patient = db.get(Patient, link.patient_id) if link and link.patient_id else None
    if patient and body.display_name != patient.display_name:
        raise HTTPException(422, "患者姓名由医生设定，不能修改。")
    if patient and patient.responsible_doctor_id != doctor.id:
        raise HTTPException(404, "患者二维码不可用。")
    if not patient:
        patient = Patient(patient_code=generate_record_code(db, Patient, Patient.patient_code, "P"), display_name=body.display_name, responsible_doctor_id=doctor.id)
        db.add(patient)
        db.flush()
        if link:
            link.used_count += 1
    if not patient.patient_user_id:
        user = User(username="p_" + secrets.token_hex(16), display_name=patient.display_name, role=UserRole.PATIENT, password_hash=hash_password(secrets.token_urlsafe(48)))
        db.add(user)
        db.flush()
        patient.patient_user_id = user.id
    else:
        user = db.get(User, patient.patient_user_id)
        if not user or not user.is_active or user.role != UserRole.PATIENT:
            raise HTTPException(403, "患者账号当前不可用，请联系医生。")
    profile = db.get(PortalProfile, patient.id)
    # A later scan of a dedicated QR must not silently overwrite an existing profile.
    if not profile:
        profile = PortalProfile(patient_id=patient.id, sex=body.sex, date_of_birth=body.date_of_birth, phone=body.phone, operator_relationship=body.operator_relationship, extra=body.extra)
        db.add(profile)
    db.add(PortalAccess(patient_id=patient.id, registration_digest=registration_digest, token_digest=digest_invitation_token(token), intake_link_id=link.id if link and link.patient_id else None, expires_at=now_utc() + timedelta(days=180)))
    db.add(PortalConsent(patient_id=patient.id, notice_version_id=notice.id, content_sha256=notice.content_sha256, context="self-enrollment", consented_at=now_utc()))
    db.commit()
    return {"access_token": token, **portal_me(patient, db)}


@router.get("/portal/me")
def me(patient: PortalPatient, db: Db, response: Response):
    response.headers["Cache-Control"] = "no-store"
    return portal_me(patient, db)


@router.put("/portal/me")
def update_me(body: ProfileRequest, request: Request, patient: PortalPatient, db: Db):
    db.execute(update(Patient).where(Patient.id == patient.id).values(display_name=Patient.display_name))
    db.expire_all()
    patient = get_portal_patient(request, db)
    profile = db.get(PortalProfile, patient.id)
    patient.display_name = body.display_name
    if not profile:
        profile = PortalProfile(patient_id=patient.id)
        db.add(profile)
    for name in ("sex", "date_of_birth", "phone", "operator_relationship", "extra"):
        setattr(profile, name, getattr(body, name))
    profile.updated_at = now_utc()
    db.commit()
    return portal_me(patient, db)


@router.post("/portal/logout")
def logout(request: Request, patient: PortalPatient, db: Db):
    access = db.scalar(select(PortalAccess).where(PortalAccess.token_digest == digest_invitation_token(request.headers["authorization"][7:])))
    access.revoked_at = now_utc()
    db.commit()
    return {"revoked": True}


@router.get("/portal/documents")
def documents(patient: PortalPatient, db: Db, response: Response):
    from patient_follow_up_system.main import patient_document_response
    response.headers["Cache-Control"] = "no-store"
    return [patient_document_response(row, db) for row in db.scalars(select(PatientDocument).where(PatientDocument.patient_id == patient.id).order_by(PatientDocument.event_date.desc(), PatientDocument.id.desc()))]


@router.post("/portal/documents", status_code=201)
def upload_document(body: DocumentRequest, request: Request, patient: PortalPatient, db: Db):
    from patient_follow_up_system.main import current_patient_notice, decode_uploaded_document, patient_document_response, patient_upload_root
    db.execute(update(Patient).where(Patient.id == patient.id).values(display_name=Patient.display_name))
    db.expire_all()
    patient = get_portal_patient(request, db)
    digest = digest_invitation_token(body.submission_key)
    existing = db.scalar(select(PortalDocumentSubmission).where(PortalDocumentSubmission.patient_id == patient.id, PortalDocumentSubmission.submission_digest == digest))
    if existing:
        return patient_document_response(db.get(PatientDocument, existing.document_id), db)
    notice = current_patient_notice(db)
    if not body.consent_given:
        raise HTTPException(422, "请勾选我已阅读并同意患者须知。")
    if not notice or notice.id != body.notice_version_id:
        raise HTTPException(409, "患者须知已更新，请查看最新版本后重试。")
    content, suffix = decode_uploaded_document(body.document_base64, body.document_mime_type)
    root = patient_upload_root()
    root.mkdir(parents=True, exist_ok=True)
    storage_name = secrets.token_hex(24) + suffix
    path = root / storage_name
    path.write_bytes(content)
    document = PatientDocument(patient_id=patient.id, submitted_by_user_id=patient.patient_user_id, notice_version_id=notice.id, event_date=body.event_date, display_label=body.display_label, patient_note=body.patient_note, original_name=Path(body.document_name.replace("\\", "/")).name, mime_type=body.document_mime_type, storage_name=storage_name, sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content), notice_content_sha256=notice.content_sha256, consented_at=now_utc(), review_status="pending", extraction_status="not_run")
    db.add(document)
    try:
        db.flush()
        db.add(PortalDocumentSubmission(patient_id=patient.id, document_id=document.id, submission_digest=digest))
        db.commit()
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return patient_document_response(document, db)


@router.get("/portal/documents/{document_id}/file", response_class=FileResponse)
def document_file(document_id: int, patient: PortalPatient, db: Db):
    from patient_follow_up_system.main import patient_upload_root
    document = db.scalar(select(PatientDocument).where(PatientDocument.id == document_id, PatientDocument.patient_id == patient.id))
    if not document:
        raise HTTPException(404, "资料不存在。")
    path = patient_upload_root() / document.storage_name
    if not path.is_file():
        raise HTTPException(404, "原件暂不可用，请联系医生。")
    return FileResponse(path, media_type=document.mime_type, filename=document.original_name, headers={"Cache-Control": "no-store"})
