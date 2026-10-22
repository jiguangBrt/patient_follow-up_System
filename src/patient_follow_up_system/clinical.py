import base64
import binascii
import hashlib
import io
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from patient_follow_up_system import clinical_ocr
from patient_follow_up_system.auth import require_roles
from patient_follow_up_system.database import get_db
from patient_follow_up_system.web_pages import page_response
from patient_follow_up_system.models import (
    ClinicalDocument,
    ClinicalField,
    ClinicalReviewEvent,
    Patient,
    PatientDemoConsent,
    PatientDocument,
    PatientIntakeLink,
    PatientIntakeSubmission,
    User,
    UserRole,
)

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
Doctor = Annotated[User, Depends(require_roles(UserRole.DOCTOR))]


@router.get("/clinical", include_in_schema=False)
def workspace(request: Request):
    return page_response("clinical.html", request)


class BufferUpload(BaseModel):
    document_name: str = Field(min_length=1, max_length=255)
    document_mime_type: Literal["image/jpeg", "image/png", "application/pdf"]
    document_base64: str = Field(min_length=4, max_length=11_200_000)


class SourceImport(BaseModel):
    source_kind: Literal["patient", "intake"]
    source_id: int = Field(ge=1)


class FieldReview(BaseModel):
    key: str
    review_status: Literal["pending", "confirmed", "corrected"]
    confirmed_value: str | None = Field(default=None, max_length=10000)


class Review(BaseModel):
    version: int = Field(ge=1)
    action: Literal["save", "file", "reject"] = "save"
    fields: list[FieldReview] = Field(default_factory=list, max_length=50)
    patient_id: int | None = Field(default=None, ge=1)
    create_patient: bool = False


class ExtractionRequest(BaseModel):
    version: int = Field(ge=1)


def buffer_root() -> Path:
    return Path(os.getenv("CLINICAL_UPLOAD_DIR", ".local/clinical_uploads"))


def original_path(doc: ClinicalDocument) -> Path:
    roots = {
        "buffer": buffer_root(),
        "patient": Path(os.getenv("PATIENT_UPLOAD_DIR", ".local/patient_uploads")),
        "intake": Path(os.getenv("INTAKE_UPLOAD_DIR", ".local/intake_uploads")),
    }
    return roots[doc.source_kind] / doc.storage_name


def own_document(db: Session, document_id: int, doctor: User) -> ClinicalDocument:
    doc = db.scalar(
        select(ClinicalDocument).where(
            ClinicalDocument.id == document_id,
            ClinicalDocument.owner_doctor_id == doctor.id,
        )
    )
    if doc is None:
        raise HTTPException(404, "资料不存在或不在负责范围内。")
    return doc


def fields_for(db: Session, document_id: int) -> list[ClinicalField]:
    return list(
        db.scalars(
            select(ClinicalField)
            .where(ClinicalField.document_id == document_id)
            .order_by(ClinicalField.id)
        )
    )


def initialize_fields(db: Session, doc: ClinicalDocument):
    db.flush()
    for key in clinical_ocr.FIELD_LABELS:
        db.add(ClinicalField(document_id=doc.id, key=key))


def field_info(field: ClinicalField) -> dict:
    return {
        "key": field.key,
        "label": clinical_ocr.FIELD_LABELS[field.key],
        "candidate_value": field.candidate_value,
        "candidate_status": field.candidate_status,
        "confidence": field.confidence,
        "evidence": field.evidence,
        "review_status": field.review_status,
        "confirmed_value": field.confirmed_value,
        "reviewed_by_id": field.reviewed_by_id,
        "reviewed_at": field.reviewed_at,
    }


def document_info(db: Session, doc: ClinicalDocument, detail: bool = True) -> dict:
    fields = fields_for(db, doc.id)
    name = next(
        (
            f.confirmed_value or f.candidate_value
            for f in fields
            if f.key == "patient_name"
        ),
        None,
    )
    data = {
        "id": doc.id,
        "patient_id": doc.patient_id,
        "status": doc.status,
        "version": doc.version,
        "candidate_name": name,
        "original_name": doc.original_name,
        "mime_type": doc.mime_type,
        "sha256": doc.sha256,
        "size_bytes": doc.size_bytes,
        "source_kind": doc.source_kind,
        "source_id": doc.source_id,
        "extraction_status": doc.extraction_status,
        "extraction_error": doc.extraction_error,
        "extraction_version": doc.extraction_version,
        "document_type": doc.document_type,
        "reviewed_by_id": doc.reviewed_by_id,
        "reviewed_at": doc.reviewed_at,
        "created_at": doc.created_at,
        "pending_fields": sum(f.review_status == "pending" for f in fields),
    }
    if detail:
        data.update(fields=[field_info(f) for f in fields], pages=doc.pages)
    return data


def commit(db: Session):
    try:
        db.commit()
    except (StaleDataError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(409, "资料已由其他操作更新，请刷新后核对重试。") from exc


@router.post("/clinical-documents", status_code=201)
def upload(request: BufferUpload, db: DB, doctor: Doctor):
    try:
        content = base64.b64decode(request.document_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(422, "文件编码无效。") from exc
    if not 0 < len(content) <= 8 * 1024 * 1024:
        raise HTTPException(413, "每份原件需为 8 MB 以内。")
    root = buffer_root()
    root.mkdir(parents=True, exist_ok=True)
    name = (
        secrets.token_hex(24)
        + {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}[
            request.document_mime_type
        ]
    )
    path = root / name
    path.write_bytes(content)
    try:
        # Fully decode before accepting an original. OCR failures still allow manual review.
        clinical_ocr.render_pages(path, request.document_mime_type)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(
            422, "文件不能解析，请使用完整 JPG、PNG 或不超过 10 页的 PDF。"
        ) from exc
    doc = ClinicalDocument(
        owner_doctor_id=doctor.id,
        source_kind="buffer",
        original_name=Path(request.document_name.replace("\\", "/")).name,
        storage_name=name,
        mime_type=request.document_mime_type,
        sha256=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
    )
    try:
        db.add(doc)
        initialize_fields(db, doc)
        db.add(
            ClinicalReviewEvent(
                document_id=doc.id,
                actor_id=doctor.id,
                action="upload",
                changes={"sha256": doc.sha256},
            )
        )
        commit(db)
    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    return document_info(db, doc)


@router.post("/clinical-documents/import")
def import_source(request: SourceImport, db: DB, doctor: Doctor):
    if request.source_kind == "patient":
        source = db.scalar(
            select(PatientDocument)
            .join(Patient, Patient.id == PatientDocument.patient_id)
            .where(
                PatientDocument.id == request.source_id,
                Patient.responsible_doctor_id == doctor.id,
            )
        )
        if source is None:
            raise HTTPException(404, "原件不在负责范围内。")
        values = {
            "original_name": source.original_name,
            "mime_type": source.mime_type,
            "storage_name": source.storage_name,
            "sha256": source.sha256,
            "size_bytes": source.size_bytes,
        }
    else:
        source = db.scalar(
            select(PatientIntakeSubmission)
            .join(PatientIntakeLink)
            .where(
                PatientIntakeSubmission.id == request.source_id,
                PatientIntakeLink.created_by_doctor_id == doctor.id,
            )
        )
        if source is None or not source.document_storage_name:
            raise HTTPException(404, "原件不在负责范围内。")
        path = (
            Path(os.getenv("INTAKE_UPLOAD_DIR", ".local/intake_uploads"))
            / source.document_storage_name
        )
        if not path.is_file():
            raise HTTPException(404, "原件不可用。")
        values = {
            "original_name": source.document_name,
            "mime_type": source.document_mime_type,
            "storage_name": source.document_storage_name,
            "sha256": source.document_sha256,
            "size_bytes": path.stat().st_size,
        }
    existing = db.scalar(
        select(ClinicalDocument).where(
            ClinicalDocument.source_kind == request.source_kind,
            ClinicalDocument.source_id == request.source_id,
        )
    )
    if existing:
        return document_info(db, own_document(db, existing.id, doctor))
    doc = ClinicalDocument(
        owner_doctor_id=doctor.id,
        source_kind=request.source_kind,
        source_id=request.source_id,
        **values,
    )
    db.add(doc)
    initialize_fields(db, doc)
    commit(db)
    return document_info(db, doc)


@router.get("/clinical-documents")
def list_documents(db: DB, doctor: Doctor):
    docs = db.scalars(
        select(ClinicalDocument)
        .where(ClinicalDocument.owner_doctor_id == doctor.id)
        .order_by(ClinicalDocument.id.desc())
    )
    return [document_info(db, doc, False) for doc in docs]


@router.get("/clinical-documents/{document_id}")
def detail(document_id: int, db: DB, doctor: Doctor):
    return document_info(db, own_document(db, document_id, doctor))


@router.get("/clinical-documents/{document_id}/file")
def original(document_id: int, db: DB, doctor: Doctor):
    doc = own_document(db, document_id, doctor)
    path = original_path(doc)
    if not path.is_file():
        raise HTTPException(404, "原件不可用。")
    return FileResponse(
        path,
        media_type=doc.mime_type,
        filename=doc.original_name,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/clinical-documents/{document_id}/pages/{page_number}")
def preview(document_id: int, page_number: int, db: DB, doctor: Doctor):
    doc = own_document(db, document_id, doctor)
    if page_number < 1 or page_number > max(1, len(doc.pages)):
        raise HTTPException(404, "页面不存在。")
    try:
        with clinical_ocr.OCR_LOCK:
            pages = clinical_ocr.render_pages(original_path(doc), doc.mime_type)
        image = pages[page_number - 1]
        rotation = doc.pages[page_number - 1]["rotation"] if doc.pages else 0
        image = image.rotate(rotation, expand=True)
        output = io.BytesIO()
        image.save(output, format="PNG")
    except Exception as exc:
        raise HTTPException(422, "预览不可用，请下载原件人工核对。") from exc
    return Response(
        output.getvalue(), media_type="image/png", headers={"Cache-Control": "no-store"}
    )


@router.post("/clinical-documents/{document_id}/extract")
def extract(document_id: int, request: ExtractionRequest, db: DB, doctor: Doctor):
    doc = own_document(db, document_id, doctor)
    if doc.status != "buffered" or doc.version != request.version:
        raise HTTPException(409, "只能提取当前版本的缓冲区资料，请刷新。")
    if any(f.review_status != "pending" or f.confirmed_value is not None for f in fields_for(db, doc.id)):
        raise HTTPException(409, "已有人工审核结果，不能重新提取覆盖。")
    path, mime_type, version, actor_id = (
        original_path(doc),
        doc.mime_type,
        doc.version,
        doctor.id,
    )
    db.rollback()  # No read transaction spans a potentially lengthy CPU operation.
    try:
        result = clinical_ocr.recognize(path, mime_type)
        error = None
    except Exception:  # noqa: BLE001 -- OCR/provider failures must retain a manual-review path.
        result = {
            "pages": [],
            "fields": [],
            "document_type": "unknown",
            "extraction_status": "failed",
            "extraction_version": clinical_ocr.OCR_VERSION,
        }
        error = "OCR 未能完成，请重试或对照原件手工录入。"
    doc = own_document(db, document_id, doctor)
    if doc.version != version or doc.status != "buffered":
        raise HTTPException(409, "提取期间资料已更新，结果未覆盖，请刷新。")
    by_key = {f.key: f for f in fields_for(db, doc.id)}
    for field in by_key.values():
        field.candidate_value = None
        field.confidence = None
        field.evidence = []
        field.candidate_status = "missing"
    for field in result["fields"]:
        for key in ("candidate_value", "confidence", "candidate_status", "evidence"):
            setattr(by_key[field["key"]], key, field[key])
    doc.pages = result["pages"]
    doc.extraction_status = result["extraction_status"]
    doc.extraction_error = error
    doc.extraction_version = result["extraction_version"]
    doc.document_type = result["document_type"]
    doc.version += 1
    db.add(
        ClinicalReviewEvent(
            document_id=doc.id,
            actor_id=actor_id,
            action="extract",
            changes={
                "version": doc.extraction_version,
                "status": doc.extraction_status,
            },
        )
    )
    commit(db)
    return document_info(db, doc)


def source_target(db: Session, doc: ClinicalDocument) -> int | None:
    if doc.source_kind == "patient":
        source = db.get(PatientDocument, doc.source_id)
        if source.review_status == "rejected":
            raise HTTPException(409, "原资料已驳回，不能入档。")
        return source.patient_id
    if doc.source_kind == "intake":
        source = db.get(PatientIntakeSubmission, doc.source_id)
        if source.status == "rejected":
            raise HTTPException(409, "建档申请已驳回，不能入档。")
        return source.created_patient_id
    return None


@router.post("/clinical-documents/{document_id}/review")
def review(document_id: int, request: Review, db: DB, doctor: Doctor):
    doc = own_document(db, document_id, doctor)
    if doc.status == "rejected" or doc.version != request.version:
        raise HTTPException(409, "资料已更新或已驳回，请刷新。")
    if doc.status == "filed" and request.action != "save":
        raise HTTPException(409, "已入档资料只能继续审核待确认字段。")
    fields = {f.key: f for f in fields_for(db, doc.id)}
    keys = [f.key for f in request.fields]
    if len(set(keys)) != len(keys) or any(k not in fields for k in keys):
        raise HTTPException(422, "字段重复或不存在。")
    changes = {}
    now = datetime.now(UTC).replace(tzinfo=None)
    for change in request.fields:
        field = fields[change.key]
        value = change.confirmed_value.strip() if change.confirmed_value is not None else None
        # A pending value is a saved draft, excluded from the filed record below.
        if change.review_status != "pending" and not value:
            raise HTTPException(422, "确认字段需要填写值；未知请保留待确认。")
        elif change.review_status == "confirmed" and (
            value != field.candidate_value
            or field.candidate_status in ("missing", "conflict")
        ):
            raise HTTPException(422, "修改或手工录入的值请选择“修改后确认”。")
        if (
            field.review_status == change.review_status
            and field.confirmed_value == value
        ):
            continue
        if doc.status == "filed" and field.review_status != "pending":
            raise HTTPException(
                409, "已入档的确认字段不能覆盖；请另建更正资料保留来源。"
            )
        changes[change.key] = {
            "before": {"status": field.review_status, "value": field.confirmed_value},
            "after": {"status": change.review_status, "value": value},
        }
        field.review_status = change.review_status
        field.confirmed_value = value
        field.reviewed_by_id = doctor.id
        field.reviewed_at = now
    if request.action == "reject":
        doc.status = "rejected"
        doc.patient_id = None
    elif request.action == "file":
        name = fields["patient_name"]
        if (
            name.review_status == "pending"
            or not name.confirmed_value
            or len(name.confirmed_value) > 100
        ):
            raise HTTPException(422, "请先确认正确姓名（100 字以内），再选择入档患者。")
        if not any(
            f.review_status != "pending" and f.key not in clinical_ocr.HEADER_KEYS
            for f in fields.values()
        ):
            raise HTTPException(422, "请至少确认一项病历内容再入档。")
        if (request.patient_id is not None) == request.create_patient:
            raise HTTPException(422, "请明确选择一位已有患者，或按确认姓名新建档案。")
        required_target = source_target(db, doc)
        if required_target and (
            request.create_patient or request.patient_id != required_target
        ):
            raise HTTPException(
                409,
                "这份资料来自已有患者/已批准申请，只能入原患者档案；姓名不符时请先人工核查。",
            )
        if request.create_patient:
            patient = Patient(
                patient_code="P-"
                + datetime.now(UTC).strftime("%Y%m%d")
                + "-"
                + secrets.token_hex(4).upper(),
                display_name=name.confirmed_value,
                responsible_doctor_id=doctor.id,
            )
            db.add(patient)
            db.flush()
        else:
            patient = db.scalar(
                select(Patient).where(
                    Patient.id == request.patient_id,
                    Patient.responsible_doctor_id == doctor.id,
                )
            )
            if patient is None:
                raise HTTPException(404, "患者不在负责范围内。")
            if patient.display_name != name.confirmed_value:
                raise HTTPException(
                    409, "确认姓名与所选患者名称不一致，请核对原件及患者身份。"
                )
        doc.patient_id, doc.status = patient.id, "filed"
        if doc.source_kind == "intake":
            submission = db.get(PatientIntakeSubmission, doc.source_id)
            submission.status, submission.created_patient_id = "approved", patient.id
            submission.reviewed_by_doctor_id, submission.reviewed_at = doctor.id, now
            for consent in db.scalars(
                select(PatientDemoConsent).where(
                    PatientDemoConsent.intake_submission_id == submission.id
                )
            ):
                consent.patient_id = patient.id
        if doc.source_kind == "patient":
            source = db.get(PatientDocument, doc.source_id)
            source.review_status = "approved"
            source.confirmed_event_date = source.event_date
            source.confirmed_label = source.display_label
            source.doctor_summary = (
                "逐字段审核内容见结构化病历档案；时间沿用患者填写的资料日期。"
            )
            source.reviewed_by_doctor_id, source.reviewed_at = doctor.id, now
        changes["patient_id"] = patient.id
    doc.reviewed_by_id, doc.reviewed_at = doctor.id, now
    doc.version += 1
    db.add(
        ClinicalReviewEvent(
            document_id=doc.id,
            actor_id=doctor.id,
            action=request.action,
            changes=changes,
        )
    )
    commit(db)
    return document_info(db, doc)


@router.get("/patients/{patient_id}/clinical-records")
def patient_records(patient_id: int, db: DB, doctor: Doctor):
    patient = db.scalar(
        select(Patient).where(
            Patient.id == patient_id, Patient.responsible_doctor_id == doctor.id
        )
    )
    if patient is None:
        raise HTTPException(404, "患者不在负责范围内。")
    output = []
    for doc in db.scalars(
        select(ClinicalDocument)
        .where(
            ClinicalDocument.patient_id == patient_id,
            ClinicalDocument.status == "filed",
        )
        .order_by(ClinicalDocument.id.desc())
    ):
        record = document_info(db, doc, False)
        record["fields"] = [
            field_info(f)
            for f in fields_for(db, doc.id)
            if f.review_status != "pending"
        ]
        # Pending candidates are visible only in the doctor's review workspace.
        output.append(record)
    return output


@router.get("/clinical-documents/{document_id}/history")
def history(document_id: int, db: DB, doctor: Doctor):
    own_document(db, document_id, doctor)
    return [
        {
            "action": event.action,
            "actor_id": event.actor_id,
            "changes": event.changes,
            "created_at": event.created_at,
        }
        for event in db.scalars(
            select(ClinicalReviewEvent)
            .where(ClinicalReviewEvent.document_id == document_id)
            .order_by(ClinicalReviewEvent.id)
        )
    ]
