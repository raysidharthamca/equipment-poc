"""SQLAlchemy ORM models — the POC database schema (Phase 1).

Design rules baked into the schema:
- Every extracted record (transaction / service_record) links back to its
  source `documents` row for auditability.
- Status colors and equipment lifecycle state live on `equipment`, computed
  by the status engine (Phase 4).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# --- Controlled vocabularies (kept as plain strings in SQLite for POC simplicity) ---

# equipment.category:        pump | compressor | valve | assembly
# equipment.status:          green | orange | red
# equipment.current_state:   available | rented | sold | in_service
# documents.doc_type:        purchase_order | rental_contract | service_record
#                            | return_record | spec_sheet | unknown
# transactions.type:         sale | rental_start | rental_return
# notifications.channel:     teams | email | in_app
# notifications.level:       warning | critical


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp (POC assumes UTC everywhere)."""
    return datetime.now(timezone.utc)


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_code: Mapped[str] = mapped_column(
        String, unique=True, index=True, nullable=False
    )  # e.g. "PMP-0041"
    name: Mapped[str | None] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String)  # pump/compressor/valve/assembly
    manufacture_date: Mapped[date | None] = mapped_column(Date)
    service_interval_days: Mapped[int] = mapped_column(
        Integer, default=180, nullable=False
    )
    last_service_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String, default="green", nullable=False
    )  # green/orange/red (computed)
    current_state: Mapped[str] = mapped_column(
        String, default="available", nullable=False
    )  # available/rented/sold/in_service
    notes: Mapped[str | None] = mapped_column(Text)

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    service_records: Mapped[list["ServiceRecord"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    doc_type: Mapped[str] = mapped_column(
        String, default="unknown", nullable=False
    )  # purchase_order/rental_contract/service_record/return_record/spec_sheet/unknown
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    file_path: Mapped[str | None] = mapped_column(String)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)  # 0..1
    raw_extraction_json: Mapped[str | None] = mapped_column(Text)
    needs_review: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="document"
    )
    service_records: Mapped[list["ServiceRecord"]] = relationship(
        back_populates="document"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipment.id"), nullable=False
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False
    )  # auditability: every record links to its source document
    type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # sale/rental_start/rental_return
    customer_name: Mapped[str | None] = mapped_column(String)
    transaction_date: Mapped[date | None] = mapped_column(Date)
    due_back_date: Mapped[date | None] = mapped_column(Date)
    amount: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String)

    equipment: Mapped["Equipment"] = relationship(back_populates="transactions")
    document: Mapped["Document"] = relationship(back_populates="transactions")


class ServiceRecord(Base):
    __tablename__ = "service_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipment.id"), nullable=False
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id"), nullable=False
    )
    service_date: Mapped[date | None] = mapped_column(Date)
    service_type: Mapped[str | None] = mapped_column(String)
    technician: Mapped[str | None] = mapped_column(String)
    next_due_date: Mapped[date | None] = mapped_column(Date)
    findings: Mapped[str | None] = mapped_column(Text)

    equipment: Mapped["Equipment"] = relationship(
        back_populates="service_records"
    )
    document: Mapped["Document"] = relationship(
        back_populates="service_records"
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipment.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)  # teams/email/in_app
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    level: Mapped[str] = mapped_column(String, nullable=False)  # warning/critical

    equipment: Mapped["Equipment"] = relationship(back_populates="notifications")
