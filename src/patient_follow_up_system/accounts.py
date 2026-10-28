from datetime import UTC
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from patient_follow_up_system.auth import hash_password, require_roles
from patient_follow_up_system.database import get_db
from patient_follow_up_system.models import AccountEvent, User, UserRole
from patient_follow_up_system.web_pages import page_response

router = APIRouter()
Admin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
DB = Annotated[Session, Depends(get_db)]


class AccountCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_][A-Za-z0-9_.-]{2,49}$")
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["doctor", "student", "patient"]
    mentor_doctor_id: int | None = Field(default=None, ge=1)

    @field_validator("display_name")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("名称不能为空")
        return value.strip()


class AccountStatus(BaseModel):
    is_active: bool


def account_info(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "mentor_doctor_id": user.mentor_doctor_id,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at.replace(tzinfo=UTC)
        if user.last_login_at
        else None,
    }


@router.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    return page_response("admin.html", request)


@router.get("/admin/accounts")
def list_accounts(db: DB, admin: Admin):
    return [
        account_info(u)
        for u in db.scalars(
            select(User)
            .where(User.role.in_([UserRole.DOCTOR, UserRole.STUDENT, UserRole.PATIENT]))
            .order_by(User.id.desc())
        )
    ]


@router.post("/admin/accounts", status_code=201)
def create_account(request: AccountCreate, db: DB, admin: Admin):
    if request.role == "student":
        mentor = db.get(User, request.mentor_doctor_id) if request.mentor_doctor_id else None
        if not mentor or mentor.role != UserRole.DOCTOR or not mentor.is_active:
            raise HTTPException(422, "学生账号必须选择一位启用的所属医生。")
    elif request.mentor_doctor_id is not None:
        raise HTTPException(422, "只有学生账号可以指定所属医生。")
    user = User(
        username=request.username,
        display_name=request.display_name,
        password_hash=hash_password(request.password),
        role=UserRole(request.role),
        mentor_doctor_id=request.mentor_doctor_id,
        is_active=True,
    )
    db.add(user)
    try:
        db.flush()
        db.add(AccountEvent(actor_id=admin.id, target_id=user.id, action="create"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "用户名已存在，请使用其他用户名。") from exc
    return account_info(user)


@router.patch("/admin/accounts/{user_id}")
def change_status(user_id: int, request: AccountStatus, db: DB, admin: Admin):
    user = db.get(User, user_id)
    if user is None or user.role not in (UserRole.DOCTOR, UserRole.STUDENT, UserRole.PATIENT):
        raise HTTPException(404, "测试账号不存在。")
    if user.is_active != request.is_active:
        user.is_active = request.is_active
        db.add(
            AccountEvent(
                actor_id=admin.id,
                target_id=user.id,
                action="enable" if request.is_active else "disable",
            )
        )
        db.commit()
    return account_info(user)
