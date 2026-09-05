import base64
import binascii
import hashlib
import os
import secrets
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIError, OpenAI
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from patient_follow_up_system.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_env,
    require_roles,
)
from patient_follow_up_system.database import get_db
from patient_follow_up_system.invitations import (
    MAX_FAILED_VERIFICATION_ATTEMPTS,
    InvitationState,
    digest_invitation_token,
    generate_invitation_token,
    generate_verification_code,
    hash_verification_code,
    invitation_qr_svg,
    invitation_state,
    verify_verification_code,
)
from patient_follow_up_system.models import (
    Encounter,
    Patient,
    PatientIntakeLink,
    PatientIntakeSubmission,
    PatientInvitation,
    User,
    UserRole,
)


load_dotenv()

app = FastAPI(
    title="Patient Follow-up System MVP",
    version="0.1.0",
)
web_root = Path(__file__).resolve().parent / "web"
app.mount("/static", StaticFiles(directory=web_root), name="static")


class HealthResponse(BaseModel):
    status: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class ChatResponse(BaseModel):
    answer: str
    model: str


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role: UserRole


class RoleDemoResponse(BaseModel):
    message: str
    username: str
    role: UserRole


class PatientCreateRequest(BaseModel):
    patient_code: str = Field(min_length=1, max_length=32)
    display_name: str = Field(min_length=1, max_length=100)


class PatientResponse(BaseModel):
    id: int
    patient_code: str
    display_name: str
    is_bound: bool
    created_at: datetime


class EncounterCreateRequest(BaseModel):
    encounter_code: str = Field(min_length=1, max_length=32)
    occurred_at: datetime
    display_label: str = Field(min_length=1, max_length=100)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        return value


class EncounterResponse(BaseModel):
    id: int
    encounter_code: str
    patient_id: int
    occurred_at: datetime
    display_label: str
    created_at: datetime


class InvitationCreateRequest(BaseModel):
    encounter_id: int | None = Field(default=None, ge=1)
    expires_in_minutes: int = Field(default=60, ge=5, le=10080)
    max_uses: int = Field(default=1, ge=1, le=10)


class InvitationCreateResponse(BaseModel):
    id: int
    invitation_token: str
    verification_code: str
    invitation_url: str
    qr_svg: str
    created_at: datetime
    expires_at: datetime
    max_uses: int
    used_count: int
    state: InvitationState


class InvitationTokenRequest(BaseModel):
    invitation_token: str = Field(min_length=20, max_length=128)


class InvitationStatusResponse(BaseModel):
    state: InvitationState


class InvitationBindRequest(BaseModel):
    invitation_token: str = Field(min_length=20, max_length=128)
    verification_code: str = Field(
        pattern=r"^(?:\d{6}|[23456789A-HJ-NP-Z]{8})$"
    )


class InvitationBindResponse(BaseModel):
    bound: bool
    already_bound: bool


class InvitationRevokeResponse(BaseModel):
    id: int
    state: InvitationState


class IntakeLinkCreateResponse(BaseModel):
    id: int
    intake_token: str
    intake_url: str
    qr_svg: str
    expires_at: datetime


class IntakeTokenRequest(BaseModel):
    intake_token: str = Field(min_length=20, max_length=128)


class IntakeSubmissionRequest(IntakeTokenRequest):
    submission_key: str = Field(min_length=20, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)
    sex: str = Field(pattern=r"^(男|女|未说明)$")
    date_of_birth: date
    operator_relationship: str = Field(pattern=r"^(本人|家属协助)$")
    notice_version: str = Field(pattern=r"^demo-notice-v1$")
    consent_given: bool
    document_name: str = Field(min_length=1, max_length=255)
    document_mime_type: str = Field(pattern=r"^(image/jpeg|image/png|application/pdf)$")
    document_base64: str = Field(min_length=4, max_length=11_000_000)


class IntakeSubmissionResponse(BaseModel):
    id: int
    display_name: str
    sex: str
    date_of_birth: date
    operator_relationship: str
    status: str
    created_at: datetime
    created_patient_id: int | None
    notice_version: str | None
    has_document: bool
    extraction_status: str


class IntakeReviewRequest(BaseModel):
    action: str = Field(pattern=r"^(approve|reject)$")
    patient_code: str | None = Field(default=None, max_length=32)
    review_note: str | None = Field(default=None, max_length=500)


def app_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def model_client() -> OpenAI:
    return OpenAI(
        base_url=app_env("MODEL_BASE_URL"),
        api_key=app_env("MODEL_API_KEY"),
        timeout=60.0,
    )


def user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


def role_demo_response(user: User, message: str) -> RoleDemoResponse:
    return RoleDemoResponse(
        message=message,
        username=user.username,
        role=user.role,
    )


def patient_response(patient: Patient) -> PatientResponse:
    return PatientResponse(
        id=patient.id,
        patient_code=patient.patient_code,
        display_name=patient.display_name,
        is_bound=patient.patient_user_id is not None,
        created_at=as_utc(patient.created_at),
    )


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def utc_for_sqlite(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def encounter_response(encounter: Encounter) -> EncounterResponse:
    return EncounterResponse(
        id=encounter.id,
        encounter_code=encounter.encounter_code,
        patient_id=encounter.patient_id,
        occurred_at=as_utc(encounter.occurred_at),
        display_label=encounter.display_label,
        created_at=as_utc(encounter.created_at),
    )


def invitation_create_response(
    invitation: PatientInvitation,
    invitation_token: str,
    verification_code: str,
    base_url: str,
) -> InvitationCreateResponse:
    invitation_url = f"{base_url.rstrip('/')}/invite#token={invitation_token}"
    return InvitationCreateResponse(
        id=invitation.id,
        invitation_token=invitation_token,
        verification_code=verification_code,
        invitation_url=invitation_url,
        qr_svg=invitation_qr_svg(invitation_url),
        created_at=as_utc(invitation.created_at),
        expires_at=as_utc(invitation.expires_at),
        max_uses=invitation.max_uses,
        used_count=invitation.used_count,
        state=InvitationState.AVAILABLE,
    )


def invitation_by_token(
    db: Session,
    invitation_token: str,
) -> PatientInvitation | None:
    if not invitation_token or len(invitation_token) > 128:
        return None
    return db.scalar(
        select(PatientInvitation).where(
            PatientInvitation.token_digest
            == digest_invitation_token(invitation_token)
        )
    )


def unavailable_invitation() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Invitation is unavailable.",
    )


def accessible_patient_or_404(
    db: Session,
    patient_id: int,
    current_user: User,
) -> Patient:
    scope_condition = (
        Patient.responsible_doctor_id == current_user.id
        if current_user.role == UserRole.DOCTOR
        else Patient.patient_user_id == current_user.id
    )
    patient = db.scalar(
        select(Patient).where(Patient.id == patient_id, scope_condition)
    )
    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient was not found in the allowed data scope.",
        )
    return patient


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/doctor", include_in_schema=False)
def doctor_page() -> FileResponse:
    return FileResponse(web_root / "doctor.html")


@app.get("/invite", include_in_schema=False)
def invitation_page() -> FileResponse:
    return FileResponse(web_root / "invite.html")


@app.get("/intake", include_in_schema=False)
def intake_page() -> FileResponse:
    return FileResponse(web_root / "intake.html")


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    model_name = app_env("MODEL_NAME")

    try:
        response = model_client().chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "你是患者随访系统的软件演示助手，不提供诊断或用药建议。",
                },
                {"role": "user", "content": request.message},
            ],
            temperature=0,
        )
    except APIError as exc:
        raise HTTPException(
            status_code=503,
            detail="Local model service is temporarily unavailable.",
        ) from exc

    answer = response.choices[0].message.content or ""
    return ChatResponse(answer=answer, model=model_name)


@app.post("/auth/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = authenticate_user(db, request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expire_minutes = int(require_env("ACCESS_TOKEN_EXPIRE_MINUTES"))
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        token_type="bearer",
        expires_in=expire_minutes * 60,
    )


@app.get("/auth/me", response_model=UserResponse)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    return user_response(current_user)


@app.post(
    "/patients",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    request: PatientCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR)),
    ],
) -> PatientResponse:
    patient = Patient(
        patient_code=request.patient_code,
        display_name=request.display_name,
        responsible_doctor_id=current_user.id,
    )
    db.add(patient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient code already exists.",
        ) from exc
    db.refresh(patient)
    return patient_response(patient)


@app.get("/patients", response_model=list[PatientResponse])
def list_patients(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR, UserRole.PATIENT)),
    ],
) -> list[PatientResponse]:
    scope_condition = (
        Patient.responsible_doctor_id == current_user.id
        if current_user.role == UserRole.DOCTOR
        else Patient.patient_user_id == current_user.id
    )
    patients = db.scalars(
        select(Patient).where(scope_condition).order_by(Patient.id)
    ).all()
    return [patient_response(patient) for patient in patients]


@app.get("/patients/{patient_id}", response_model=PatientResponse)
def read_patient(
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR, UserRole.PATIENT)),
    ],
) -> PatientResponse:
    patient = accessible_patient_or_404(db, patient_id, current_user)
    return patient_response(patient)


@app.post(
    "/patients/{patient_id}/invitations",
    response_model=InvitationCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_patient_invitation(
    patient_id: int,
    request: InvitationCreateRequest,
    http_request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR)),
    ],
) -> InvitationCreateResponse:
    patient = accessible_patient_or_404(db, patient_id, current_user)

    if request.encounter_id is not None:
        encounter = db.scalar(
            select(Encounter).where(
                Encounter.id == request.encounter_id,
                Encounter.patient_id == patient.id,
                Encounter.doctor_id == current_user.id,
            )
        )
        if encounter is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Encounter was not found in the allowed data scope.",
            )

    invitation_token = generate_invitation_token()
    verification_code = generate_verification_code()
    expires_at = datetime.now(UTC) + timedelta(
        minutes=request.expires_in_minutes
    )
    invitation = PatientInvitation(
        token_digest=digest_invitation_token(invitation_token),
        verification_code_hash=hash_verification_code(verification_code),
        patient_id=patient.id,
        encounter_id=request.encounter_id,
        created_by_doctor_id=current_user.id,
        expires_at=utc_for_sqlite(expires_at),
        max_uses=request.max_uses,
    )
    db.add(invitation)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invitation could not be created.",
        ) from exc
    db.refresh(invitation)
    return invitation_create_response(
        invitation,
        invitation_token,
        verification_code,
        str(http_request.base_url),
    )


@app.post(
    "/invitations/status",
    response_model=InvitationStatusResponse,
)
def read_invitation_status(
    request: InvitationTokenRequest,
    db: Annotated[Session, Depends(get_db)],
) -> InvitationStatusResponse:
    invitation = invitation_by_token(db, request.invitation_token)
    state = (
        InvitationState.UNAVAILABLE
        if invitation is None
        else invitation_state(invitation)
    )
    return InvitationStatusResponse(state=state)


@app.post(
    "/invitations/{invitation_id}/revoke",
    response_model=InvitationRevokeResponse,
)
def revoke_invitation(
    invitation_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR)),
    ],
) -> InvitationRevokeResponse:
    invitation = db.scalar(
        select(PatientInvitation).where(
            PatientInvitation.id == invitation_id,
            PatientInvitation.created_by_doctor_id == current_user.id,
        )
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation was not found in the allowed data scope.",
        )
    if invitation.revoked_at is None:
        invitation.revoked_at = utc_for_sqlite(datetime.now(UTC))
        db.commit()
    return InvitationRevokeResponse(
        id=invitation.id,
        state=InvitationState.REVOKED,
    )


@app.post(
    "/invitations/bind",
    response_model=InvitationBindResponse,
)
def bind_patient_invitation(
    request: InvitationBindRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.PATIENT)),
    ],
) -> InvitationBindResponse:
    invitation = invitation_by_token(db, request.invitation_token)
    if invitation is None:
        raise unavailable_invitation()

    patient = db.get(Patient, invitation.patient_id)
    if patient is None:
        raise unavailable_invitation()

    state = invitation_state(invitation)
    if state in {
        InvitationState.EXPIRED,
        InvitationState.REVOKED,
        InvitationState.LOCKED,
    }:
        raise unavailable_invitation()
    if state == InvitationState.EXHAUSTED:
        if patient.patient_user_id == current_user.id:
            return InvitationBindResponse(bound=True, already_bound=True)
        raise unavailable_invitation()

    if not verify_verification_code(
        request.verification_code,
        invitation.verification_code_hash,
    ):
        invitation.failed_verification_attempts += 1
        if (
            invitation.failed_verification_attempts
            >= MAX_FAILED_VERIFICATION_ATTEMPTS
        ):
            invitation.locked_at = utc_for_sqlite(datetime.now(UTC))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation verification failed.",
        )

    existing_patient = db.scalar(
        select(Patient).where(Patient.patient_user_id == current_user.id)
    )
    if patient.patient_user_id not in (None, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient profile cannot be bound to this account.",
        )
    if existing_patient is not None and existing_patient.id != patient.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This account is already bound to another patient profile.",
        )

    already_bound = patient.patient_user_id == current_user.id
    patient.patient_user_id = current_user.id
    invitation.used_count += 1
    invitation.last_used_at = utc_for_sqlite(datetime.now(UTC))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Patient profile could not be bound.",
        ) from exc
    return InvitationBindResponse(
        bound=True,
        already_bound=already_bound,
    )


def intake_submission_response(
    submission: PatientIntakeSubmission,
) -> IntakeSubmissionResponse:
    return IntakeSubmissionResponse(
        id=submission.id,
        display_name=submission.display_name,
        sex=submission.sex,
        date_of_birth=submission.date_of_birth,
        operator_relationship=submission.operator_relationship,
        status=submission.status,
        created_at=as_utc(submission.created_at),
        created_patient_id=submission.created_patient_id,
        notice_version=submission.notice_version,
        has_document=bool(submission.document_storage_name),
        extraction_status=submission.extraction_status,
    )


@app.post("/intake-links", response_model=IntakeLinkCreateResponse, status_code=201)
def create_intake_link(
    http_request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
) -> IntakeLinkCreateResponse:
    token = generate_invitation_token()
    expires_at = datetime.now(UTC) + timedelta(days=7)
    link = PatientIntakeLink(
        token_digest=digest_invitation_token(token),
        created_by_doctor_id=current_user.id,
        expires_at=utc_for_sqlite(expires_at),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    url = f"{str(http_request.base_url).rstrip('/')}/intake#token={token}"
    return IntakeLinkCreateResponse(
        id=link.id,
        intake_token=token,
        intake_url=url,
        qr_svg=invitation_qr_svg(url),
        expires_at=as_utc(link.expires_at),
    )


@app.post("/intake-links/status", response_model=InvitationStatusResponse)
def read_intake_link_status(
    request: IntakeTokenRequest,
    db: Annotated[Session, Depends(get_db)],
) -> InvitationStatusResponse:
    link = db.scalar(select(PatientIntakeLink).where(PatientIntakeLink.token_digest == digest_invitation_token(request.intake_token)))
    if link is None:
        return InvitationStatusResponse(state=InvitationState.UNAVAILABLE)
    now = utc_for_sqlite(datetime.now(UTC))
    state = InvitationState.AVAILABLE
    if link.revoked_at is not None:
        state = InvitationState.REVOKED
    elif link.expires_at <= now:
        state = InvitationState.EXPIRED
    elif link.used_count >= link.max_submissions:
        state = InvitationState.EXHAUSTED
    return InvitationStatusResponse(state=state)


@app.post("/intake-links/{link_id}/revoke", response_model=InvitationRevokeResponse)
def revoke_intake_link(
    link_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
) -> InvitationRevokeResponse:
    link = db.scalar(select(PatientIntakeLink).where(PatientIntakeLink.id == link_id, PatientIntakeLink.created_by_doctor_id == current_user.id))
    if link is None:
        raise HTTPException(status_code=404, detail="Intake link was not found in the allowed data scope.")
    if link.revoked_at is None:
        link.revoked_at = utc_for_sqlite(datetime.now(UTC))
        db.commit()
    return InvitationRevokeResponse(id=link.id, state=InvitationState.REVOKED)


@app.post("/intake-submissions", response_model=IntakeSubmissionResponse, status_code=201)
def submit_intake(
    request: IntakeSubmissionRequest,
    db: Annotated[Session, Depends(get_db)],
) -> IntakeSubmissionResponse:
    link = db.scalar(select(PatientIntakeLink).where(PatientIntakeLink.token_digest == digest_invitation_token(request.intake_token)))
    now = utc_for_sqlite(datetime.now(UTC))
    if link is None or link.revoked_at is not None or link.expires_at <= now or link.used_count >= link.max_submissions:
        raise unavailable_invitation()
    submission_digest = digest_invitation_token(request.submission_key)
    existing = db.scalar(select(PatientIntakeSubmission).where(PatientIntakeSubmission.submission_digest == submission_digest))
    if existing is not None:
        return intake_submission_response(existing)
    if not request.consent_given:
        raise HTTPException(status_code=422, detail="Demo notice consent is required.")
    try:
        document_bytes = base64.b64decode(request.document_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Document data is invalid.") from exc
    if not document_bytes or len(document_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Document must be 8 MB or smaller.")
    signatures = {
        "image/jpeg": document_bytes.startswith(b"\xff\xd8\xff"),
        "image/png": document_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
        "application/pdf": document_bytes.startswith(b"%PDF-"),
    }
    if not signatures[request.document_mime_type]:
        raise HTTPException(status_code=422, detail="Document type does not match its content.")
    upload_root = Path(".local/intake_uploads")
    upload_root.mkdir(parents=True, exist_ok=True)
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}[request.document_mime_type]
    storage_name = f"{secrets.token_hex(24)}{suffix}"
    (upload_root / storage_name).write_bytes(document_bytes)
    submission = PatientIntakeSubmission(
        intake_link_id=link.id,
        submission_digest=submission_digest,
        display_name=request.display_name,
        sex=request.sex,
        date_of_birth=request.date_of_birth,
        operator_relationship=request.operator_relationship,
        notice_version=request.notice_version,
        consented_at=utc_for_sqlite(datetime.now(UTC)),
        document_name=Path(request.document_name).name,
        document_mime_type=request.document_mime_type,
        document_storage_name=storage_name,
        document_sha256=hashlib.sha256(document_bytes).hexdigest(),
    )
    link.used_count += 1
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return intake_submission_response(submission)


@app.get("/intake-submissions", response_model=list[IntakeSubmissionResponse])
def list_intake_submissions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
) -> list[IntakeSubmissionResponse]:
    items = db.scalars(
        select(PatientIntakeSubmission)
        .join(PatientIntakeLink, PatientIntakeSubmission.intake_link_id == PatientIntakeLink.id)
        .where(PatientIntakeLink.created_by_doctor_id == current_user.id)
        .order_by(PatientIntakeSubmission.id.desc())
    ).all()
    return [intake_submission_response(item) for item in items]


@app.get("/intake-submissions/{submission_id}/document", response_class=FileResponse)
def read_intake_document(
    submission_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
) -> FileResponse:
    submission = db.scalar(
        select(PatientIntakeSubmission)
        .join(PatientIntakeLink, PatientIntakeSubmission.intake_link_id == PatientIntakeLink.id)
        .where(PatientIntakeSubmission.id == submission_id, PatientIntakeLink.created_by_doctor_id == current_user.id)
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Intake document was not found in the allowed data scope.")
    if not submission.document_storage_name or not submission.document_mime_type or not submission.document_name:
        raise HTTPException(status_code=404, detail="Intake document is unavailable.")
    path = Path(".local/intake_uploads") / submission.document_storage_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Intake document is unavailable.")
    return FileResponse(path, media_type=submission.document_mime_type, filename=submission.document_name)


@app.post("/intake-submissions/{submission_id}/review", response_model=IntakeSubmissionResponse)
def review_intake_submission(
    submission_id: int,
    request: IntakeReviewRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_roles(UserRole.DOCTOR))],
) -> IntakeSubmissionResponse:
    submission = db.scalar(
        select(PatientIntakeSubmission)
        .join(PatientIntakeLink, PatientIntakeSubmission.intake_link_id == PatientIntakeLink.id)
        .where(PatientIntakeSubmission.id == submission_id, PatientIntakeLink.created_by_doctor_id == current_user.id)
    )
    if submission is None:
        raise HTTPException(status_code=404, detail="Intake submission was not found in the allowed data scope.")
    if submission.status != "pending":
        return intake_submission_response(submission)
    if request.action == "reject":
        submission.status = "rejected"
    else:
        if not request.patient_code:
            raise HTTPException(status_code=422, detail="Patient code is required for approval.")
        if not submission.notice_version or not submission.document_storage_name:
            raise HTTPException(status_code=409, detail="Submission is incomplete and cannot be approved.")
        patient = Patient(
            patient_code=request.patient_code,
            display_name=submission.display_name,
            responsible_doctor_id=current_user.id,
        )
        db.add(patient)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Patient code already exists.") from exc
        submission.status = "approved"
        submission.created_patient_id = patient.id
    submission.reviewed_by_doctor_id = current_user.id
    submission.reviewed_at = utc_for_sqlite(datetime.now(UTC))
    submission.review_note = request.review_note
    db.commit()
    db.refresh(submission)
    return intake_submission_response(submission)


@app.post(
    "/patients/{patient_id}/encounters",
    response_model=EncounterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_encounter(
    patient_id: int,
    request: EncounterCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR)),
    ],
) -> EncounterResponse:
    patient = accessible_patient_or_404(db, patient_id, current_user)
    encounter = Encounter(
        encounter_code=request.encounter_code,
        patient_id=patient.id,
        doctor_id=current_user.id,
        occurred_at=utc_for_sqlite(request.occurred_at),
        display_label=request.display_label,
    )
    db.add(encounter)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Encounter code already exists.",
        ) from exc
    db.refresh(encounter)
    return encounter_response(encounter)


@app.get(
    "/patients/{patient_id}/encounters",
    response_model=list[EncounterResponse],
)
def list_encounters(
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR, UserRole.PATIENT)),
    ],
) -> list[EncounterResponse]:
    patient = accessible_patient_or_404(db, patient_id, current_user)
    encounters = db.scalars(
        select(Encounter)
        .where(Encounter.patient_id == patient.id)
        .order_by(Encounter.occurred_at, Encounter.id)
    ).all()
    return [encounter_response(encounter) for encounter in encounters]


@app.get("/demo/admin", response_model=RoleDemoResponse)
def admin_demo(
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.ADMIN)),
    ],
) -> RoleDemoResponse:
    return role_demo_response(current_user, "Admin demo access granted.")


@app.get("/demo/doctor", response_model=RoleDemoResponse)
def doctor_demo(
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.DOCTOR)),
    ],
) -> RoleDemoResponse:
    return role_demo_response(current_user, "Doctor demo access granted.")


@app.get("/demo/patient", response_model=RoleDemoResponse)
def patient_demo(
    current_user: Annotated[
        User,
        Depends(require_roles(UserRole.PATIENT)),
    ],
) -> RoleDemoResponse:
    return role_demo_response(current_user, "Patient demo access granted.")
