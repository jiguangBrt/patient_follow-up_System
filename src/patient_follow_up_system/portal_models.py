"""Private browser access and doctor enrollment links; no patient data in public links."""
from datetime import date, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from patient_follow_up_system.database import Base


class DoctorEnrollmentLink(Base):
    __tablename__ = "doctor_enrollment_links"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    nonce: Mapped[str] = mapped_column(String(64), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class PortalAccess(Base):
    __tablename__ = "portal_access"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    registration_digest: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    intake_link_id: Mapped[int | None] = mapped_column(ForeignKey("patient_intake_links.id"), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class PortalProfile(Base):
    __tablename__ = "portal_profiles"
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    sex: Mapped[str] = mapped_column(String(20), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    operator_relationship: Mapped[str] = mapped_column(String(30), nullable=False)
    extra: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class PortalConsent(Base):
    __tablename__ = "portal_consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True, nullable=False)
    notice_version_id: Mapped[int] = mapped_column(ForeignKey("patient_notice_versions.id"), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    context: Mapped[str] = mapped_column(String(40), nullable=False)
    consented_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PortalDocumentSubmission(Base):
    __tablename__ = "portal_document_submissions"
    __table_args__ = (UniqueConstraint("patient_id", "submission_digest", name="uq_portal_document_submission"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False)
    document_id: Mapped[int] = mapped_column(ForeignKey("patient_documents.id"), unique=True, nullable=False)
    submission_digest: Mapped[str] = mapped_column(String(64), nullable=False)
