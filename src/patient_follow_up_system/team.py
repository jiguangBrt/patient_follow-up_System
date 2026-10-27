"""Doctors manage their own students and dated patient grants."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from patient_follow_up_system.accounts import AccountCreate, AccountStatus, account_info
from patient_follow_up_system.auth import hash_password, require_roles
from patient_follow_up_system.database import get_db
from patient_follow_up_system.models import AccountEvent, PatientGrant, User, UserRole
from patient_follow_up_system.web_pages import page_response

router = APIRouter()
DB = Annotated[Session, Depends(get_db)]
Doctor = Annotated[User, Depends(require_roles(UserRole.DOCTOR))]


class StudentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]{2,49}$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("display_name")
    @classmethod
    def nonblank(cls, value):
        return AccountCreate.nonblank(value)


class GrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: int = Field(ge=1)
    note: str = Field(default="", max_length=300)
    can_view: bool = True
    can_edit: bool = False
    can_review: bool = False
    is_permanent: bool = False
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def valid_permissions(self):
        self.note = self.note.strip()
        if not self.can_view and (self.can_edit or self.can_review):
            raise ValueError("录入或审核权限需要同时开启查看")
        if self.is_permanent:
            self.starts_at = self.ends_at = None
            return self
        if self.starts_at is None or self.ends_at is None:
            raise ValueError("请选择开始、截止日期，或勾选永久有效")
        if self.starts_at.tzinfo is None or self.ends_at.tzinfo is None:
            raise ValueError("授权时间必须包含时区")
        self.starts_at = self.starts_at.astimezone(UTC).replace(tzinfo=None)
        self.ends_at = self.ends_at.astimezone(UTC).replace(tzinfo=None)
        if self.ends_at <= self.starts_at or self.ends_at <= datetime.now(UTC).replace(
            tzinfo=None
        ):
            raise ValueError("截止日期不能早于开始日期或已经到期")
        return self


def own_student(db, doctor, student_id):
    student = db.scalar(
        select(User).where(
            User.id == student_id,
            User.role == UserRole.STUDENT,
            User.mentor_doctor_id == doctor.id,
        )
    )
    if not student:
        raise HTTPException(404, "学生不在你的团队内。")
    return student


def grant_info(grant):
    data = {
        key: getattr(grant, key)
        for key in (
            "id",
            "student_id",
            "patient_id",
            "granted_by_id",
            "purpose",
            "can_view",
            "can_edit",
            "can_review",
            "revoked_by_id",
        )
    }
    for key in ("starts_at", "ends_at", "created_at", "revoked_at"):
        value = getattr(grant, key)
        data[key] = value.replace(tzinfo=UTC) if value else None
    data["note"] = grant.purpose
    data["is_permanent"] = grant.starts_at is None and grant.ends_at is None
    data["scope"] = "doctor" if grant.patient_id is None else "patient"
    now = datetime.now(UTC).replace(tzinfo=None)
    data["state"] = (
        "revoked"
        if grant.revoked_at
        else "expired"
        if grant.ends_at is not None and grant.ends_at <= now
        else "scheduled"
        if grant.starts_at is not None and grant.starts_at > now
        else "active"
    )
    return data


@router.get("/team", include_in_schema=False)
def team_page(request: Request):
    return page_response("team.html", request)


@router.get("/doctor/students")
def students(db: DB, doctor: Doctor):
    return [
        account_info(u)
        for u in db.scalars(
            select(User)
            .where(User.role == UserRole.STUDENT, User.mentor_doctor_id == doctor.id)
            .order_by(User.id.desc())
        )
    ]


@router.post("/doctor/students", status_code=201)
def create_student(request: StudentCreate, db: DB, doctor: Doctor):
    user = User(
        **request.model_dump(exclude={"password"}),
        password_hash=hash_password(request.password),
        role=UserRole.STUDENT,
        mentor_doctor_id=doctor.id,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
        db.add(AccountEvent(actor_id=doctor.id, target_id=user.id, action="create"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "用户名已存在，请使用其他用户名。") from exc
    return account_info(user)


@router.patch("/doctor/students/{student_id}")
def student_status(student_id: int, request: AccountStatus, db: DB, doctor: Doctor):
    student = own_student(db, doctor, student_id)
    if student.is_active != request.is_active:
        student.is_active = request.is_active
        db.add(
            AccountEvent(
                actor_id=doctor.id,
                target_id=student.id,
                action="enable" if request.is_active else "disable",
            )
        )
        db.commit()
    return account_info(student)


@router.get("/doctor/patient-grants", include_in_schema=False)
@router.get("/doctor/student-permissions")
def grants(db: DB, doctor: Doctor):
    return [
        grant_info(g)
        for g in db.scalars(
            select(PatientGrant)
            .where(PatientGrant.granted_by_id == doctor.id)
            .order_by(PatientGrant.id.desc())
        )
    ]


@router.post("/doctor/student-permissions", status_code=201)
def grant_student(request: GrantCreate, db: DB, doctor: Doctor):
    # Serialize settings updates on this student before reading/replacing grants.
    # This prevents parallel saves from leaving two configurations active.
    db.execute(
        update(User)
        .where(
            User.id == request.student_id,
            User.role == UserRole.STUDENT,
            User.mentor_doctor_id == doctor.id,
        )
        .values(is_active=User.is_active)
    )
    student = own_student(db, doctor, request.student_id)
    if not student.is_active:
        raise HTTPException(422, "请先启用学生账号。")
    now = datetime.now(UTC).replace(tzinfo=None)
    db.execute(
        update(PatientGrant)
        .where(
            PatientGrant.student_id == student.id,
            PatientGrant.granted_by_id == doctor.id,
            PatientGrant.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoked_by_id=doctor.id)
    )
    grant = PatientGrant(
        **request.model_dump(exclude={"note", "is_permanent"}),
        patient_id=None,
        purpose=request.note,
        granted_by_id=doctor.id,
    )
    db.add(grant)
    db.commit()
    return grant_info(grant)


@router.post("/doctor/patient-grants/{grant_id}/revoke", include_in_schema=False)
@router.post("/doctor/student-permissions/{grant_id}/revoke")
def revoke(grant_id: int, db: DB, doctor: Doctor):
    grant = db.scalar(
        select(PatientGrant).where(
            PatientGrant.id == grant_id, PatientGrant.granted_by_id == doctor.id
        )
    )
    if not grant:
        raise HTTPException(404, "授权记录不存在。")
    if grant.revoked_at is None:
        grant.revoked_at = datetime.now(UTC).replace(tzinfo=None)
        grant.revoked_by_id = doctor.id
        db.commit()
    return grant_info(grant)
