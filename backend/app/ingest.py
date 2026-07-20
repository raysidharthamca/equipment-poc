"""Ingestion service: turn an extracted PDF into DB rows, then recompute
status and fire notifications.

This is the shared core behind POST /documents/upload (Phase 3) and seed.py
(Phase 7). Every stored transaction / service record links back to its source
document (auditability is a selling point).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notify, status
from app.extraction import ExtractionResult, run_pipeline
from app.models import Document, Equipment, ServiceRecord, Transaction

DUE_BACK_ALERT_DAYS = 7


def get_or_create_equipment(db: Session, code: str) -> tuple[Equipment, bool]:
    """Return (equipment, created). Codes are the fleet's stable identity."""
    code = code.strip().upper()
    eq = db.execute(
        select(Equipment).where(Equipment.equipment_code == code)
    ).scalars().first()
    if eq is not None:
        return eq, False
    eq = Equipment(equipment_code=code, status="green", current_state="available")
    db.add(eq)
    db.flush()  # assign id
    return eq, True


def ingest_pdf(
    db: Session,
    *,
    filename: str,
    pdf_bytes: bytes,
    file_path: Optional[str] = None,
    source_id: Optional[str] = None,
    ref_date: Optional[date] = None,
) -> dict:
    """Full pipeline: extract -> persist -> recompute status -> notify.
    Caller commits. Returns a JSON-serializable result summary."""
    ref = ref_date or status.today()
    result: ExtractionResult = run_pipeline(pdf_bytes)

    doc = Document(
        filename=filename,
        source_id=source_id,
        doc_type=result.doc_type,
        file_path=file_path,
        extraction_confidence=result.confidence,
        raw_extraction_json=result.raw_json,
        needs_review=result.needs_review,
    )
    db.add(doc)
    db.flush()

    affected: dict[int, Equipment] = {}
    created_unknown = False

    if result.data is not None:
        created_unknown = _apply_records(db, doc, result, affected)

    # Workflow rule: an unrecognized document (no structured data) always needs
    # a human check. Newly created equipment codes are recorded but don't flood
    # the review queue — the confidence signal drives that.
    if result.data is None and not doc.needs_review:
        doc.needs_review = True

    # Recompute status for touched equipment and collect the changes.
    changes = []
    for eq in affected.values():
        change = status.recompute_one(eq, db, ref)
        changes.append(change)

    db.flush()

    # Notifications: fire when a status worsened to orange/red, and when a
    # rental due-back is within the alert window.
    fired = []
    for change in changes:
        if change.worsened and change.new_status in ("orange", "red"):
            eq = affected[change.equipment_id]
            n = notify.notify_status_change(db, eq, change.new_status, change.days_until_due)
            if n is not None:
                fired.append(n)

    for eq in affected.values():
        note = _maybe_due_back(db, eq, ref)
        if note is not None:
            fired.append(note)

    db.flush()

    return {
        "document": {
            "id": doc.id,
            "filename": doc.filename,
            "doc_type": doc.doc_type,
            "extraction_confidence": doc.extraction_confidence,
            "needs_review": doc.needs_review,
        },
        "extraction": result.data.model_dump(mode="json") if result.data else None,
        "review_reason": result.review_reason,
        "affected_equipment": [
            {"id": eq.id, "equipment_code": eq.equipment_code,
             "status": eq.status, "current_state": eq.current_state}
            for eq in affected.values()
        ],
        "status_changes": [
            {"equipment_code": c.equipment_code, "old": c.old_status,
             "new": c.new_status, "days_until_due": c.days_until_due}
            for c in changes
        ],
        "notifications": [
            {"equipment_id": n.equipment_id, "level": n.level, "message": n.message}
            for n in fired
        ],
    }


def _apply_records(db: Session, doc: Document, result: ExtractionResult,
                   affected: dict[int, Equipment]) -> bool:
    """Write transactions / service records and apply state transitions.
    Returns True if any equipment code was newly created."""
    data = result.data
    dtype = result.doc_type
    created_any = False

    def touch(code: str) -> Equipment:
        nonlocal created_any
        eq, created = get_or_create_equipment(db, code)
        created_any = created_any or created
        affected[eq.id] = eq
        return eq

    if dtype == "purchase_order":
        for item in data.line_items:
            if not item.equipment_code:
                continue
            eq = touch(item.equipment_code)
            if item.description and not eq.name:
                eq.name = item.description
            amount = None
            if item.unit_price is not None:
                amount = item.unit_price * (item.qty or 1)
            db.add(Transaction(
                equipment_id=eq.id, document_id=doc.id, type="sale",
                customer_name=data.customer_name, transaction_date=data.order_date,
                amount=amount, currency=data.currency,
            ))
            if data.is_sale:
                eq.current_state = "sold"

    elif dtype == "rental_contract":
        for code in data.equipment_codes:
            eq = touch(code)
            db.add(Transaction(
                equipment_id=eq.id, document_id=doc.id, type="rental_start",
                customer_name=data.customer_name, transaction_date=data.start_date,
                due_back_date=data.due_back_date, amount=data.monthly_rate,
                currency=data.currency,
            ))
            eq.current_state = "rented"

    elif dtype == "service_record":
        if data.equipment_code:
            eq = touch(data.equipment_code)
            db.add(ServiceRecord(
                equipment_id=eq.id, document_id=doc.id,
                service_date=data.service_date, service_type=data.service_type,
                technician=data.technician, next_due_date=data.next_due_date,
                findings=data.findings,
            ))
            if data.service_date and (
                eq.last_service_date is None or data.service_date > eq.last_service_date
            ):
                eq.last_service_date = data.service_date
            if eq.current_state == "in_service":
                eq.current_state = "available"

    elif dtype == "return_record":
        for code in data.equipment_codes:
            eq = touch(code)
            db.add(Transaction(
                equipment_id=eq.id, document_id=doc.id, type="rental_return",
                transaction_date=data.return_date,
            ))
            eq.current_state = "available"

    elif dtype == "spec_sheet":
        if data.equipment_code:
            eq = touch(data.equipment_code)
            if data.name:
                eq.name = data.name
            if data.category:
                eq.category = data.category
            if data.service_interval_days:
                eq.service_interval_days = data.service_interval_days
            if data.specs and not eq.notes:
                eq.notes = "; ".join(f"{k}: {v}" for k, v in data.specs.items())

    return created_any


def _maybe_due_back(db: Session, eq: Equipment, ref: date):
    """Fire a due-back warning if this equipment has a rental due within the
    alert window and isn't already returned."""
    if eq.current_state != "rented":
        return None
    stmt = (
        select(Transaction)
        .where(Transaction.equipment_id == eq.id,
               Transaction.type == "rental_start",
               Transaction.due_back_date.isnot(None))
        .order_by(Transaction.id.desc())
        .limit(1)
    )
    txn = db.execute(stmt).scalars().first()
    if txn is None or txn.due_back_date is None:
        return None
    days_left = (txn.due_back_date - ref).days
    if 0 <= days_left <= DUE_BACK_ALERT_DAYS:
        return notify.notify_due_back(db, eq, days_left)
    return None
