"""Append-only disease records, separate from OCR candidates and enrollment."""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from patient_follow_up_system.database import Base


class GastritisRecord(Base):
    __tablename__ = "gastritis_records"
    __table_args__ = (UniqueConstraint("patient_id", "version", name="uq_gastritis_patient_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    version: Mapped[int]
    recorded_on: Mapped[date] = mapped_column(Date)
    payload: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())


class GastritisOptionConfirmation(Base):
    __tablename__ = "gastritis_option_confirmations"
    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    schema_version: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.current_timestamp())
