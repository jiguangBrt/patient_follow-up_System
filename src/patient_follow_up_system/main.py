import os
from datetime import UTC, datetime
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
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
from patient_follow_up_system.models import Encounter, Patient, User, UserRole


load_dotenv()

app = FastAPI(
    title="Patient Follow-up System MVP",
    version="0.1.0",
)


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
