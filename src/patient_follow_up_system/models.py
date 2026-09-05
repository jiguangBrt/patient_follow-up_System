from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from patient_follow_up_system.database import Base


class UserRole(StrEnum):
    ADMIN = "admin"
    DOCTOR = "doctor"
    PATIENT = "patient"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            values_callable=lambda enum_type: [role.value for role in enum_type],
        ),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    patient_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        unique=True,
        index=True,
        nullable=True,
    )
    responsible_doctor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[int] = mapped_column(primary_key=True)
    encounter_code: Mapped[str] = mapped_column(
        String(32),
        unique=True,
        index=True,
        nullable=False,
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    doctor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    display_label: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )


class PatientInvitation(Base):
    __tablename__ = "patient_invitations"
    __table_args__ = (
        CheckConstraint("max_uses > 0", name="ck_invitation_max_uses_positive"),
        CheckConstraint("used_count >= 0", name="ck_invitation_used_count_nonnegative"),
        CheckConstraint(
            "used_count <= max_uses",
            name="ck_invitation_used_count_within_limit",
        ),
        CheckConstraint(
            "failed_verification_attempts >= 0",
            name="ck_invitation_failed_attempts_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_digest: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    verification_code_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    patient_id: Mapped[int] = mapped_column(
        ForeignKey("patients.id"),
        index=True,
        nullable=False,
    )
    encounter_id: Mapped[int | None] = mapped_column(
        ForeignKey("encounters.id"),
        index=True,
        nullable=True,
    )
    created_by_doctor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    max_uses: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default="1",
        nullable=False,
    )
    used_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    failed_verification_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PatientIntakeLink(Base):
    __tablename__ = "patient_intake_links"
    __table_args__ = (
        CheckConstraint("max_submissions > 0", name="ck_intake_link_max_positive"),
        CheckConstraint("used_count >= 0", name="ck_intake_link_used_nonnegative"),
        CheckConstraint("used_count <= max_submissions", name="ck_intake_link_within_limit"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_by_doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_submissions: Mapped[int] = mapped_column(Integer, default=100, server_default="100", nullable=False)
    used_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PatientIntakeSubmission(Base):
    __tablename__ = "patient_intake_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    intake_link_id: Mapped[int] = mapped_column(ForeignKey("patient_intake_links.id"), index=True, nullable=False)
    submission_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    submitted_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(nullable=False)
    operator_relationship: Mapped[str] = mapped_column(String(30), nullable=False)
    notice_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_storage_name: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    document_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending", index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False)
    reviewed_by_doctor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_patient_id: Mapped[int | None] = mapped_column(ForeignKey("patients.id"), unique=True, nullable=True)
