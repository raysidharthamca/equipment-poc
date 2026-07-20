"""FastAPI application: ingestion, admin, and portal read APIs.

Routes:
  GET  /health
  POST /documents/upload          -> full extract->persist->status->notify pipeline
  GET  /equipment                 -> fleet list (with days_until_due, summary)
  GET  /equipment/{id}            -> detail: specs, history, source docs, explanation
  GET  /documents                 -> all documents
  GET  /documents/{id}            -> one document (+ raw extraction json)
  GET  /documents/{id}/file       -> the source PDF
  GET  /review-queue              -> documents needing human review
  POST /documents/{id}/approve    -> apply corrections / clear review flag
  GET  /notifications             -> reverse-chron alert feed
  POST /admin/recompute           -> force a status recompute (demo lever)
"""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import notify, source, status
from app.config import settings
from app.database import SessionLocal, get_db, init_db
from app.ingest import ingest_pdf
from app.models import Document, Equipment, Notification, ServiceRecord, Transaction

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")

scheduler: Optional[BackgroundScheduler] = None


def recompute_and_notify(db: Session, ref: Optional[date] = None) -> list[dict]:
    """Recompute all statuses; fire alerts for any that worsened. Commits."""
    changes = status.recompute_all(db, ref)
    fired = []
    for change in changes:
        if change.worsened and change.new_status in ("orange", "red"):
            eq = db.get(Equipment, change.equipment_id)
            n = notify.notify_status_change(db, eq, change.new_status, change.days_until_due)
            if n is not None:
                fired.append(change)
    db.commit()
    return [
        {"equipment_code": c.equipment_code, "old": c.old_status, "new": c.new_status}
        for c in changes
    ]


def _daily_recompute() -> None:
    db = SessionLocal()
    try:
        recompute_and_notify(db)
    finally:
        db.close()


def _poll_source() -> None:
    """Scheduled ingestion: pull any new PDFs from the configured source
    (OneDrive folder / local inbox) and run them through the pipeline."""
    db = SessionLocal()
    try:
        summary = source.scan_and_ingest(db)
        if summary["ingested"] or summary["errors"]:
            print(f"[ingest] {summary}")
    except Exception as e:
        print(f"[ingest] source scan failed: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    init_db()
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(_daily_recompute, "interval", hours=24, id="daily_recompute")
    if settings.INGEST_POLL_MINUTES > 0:
        scheduler.add_job(
            _poll_source, "interval", minutes=settings.INGEST_POLL_MINUTES,
            id="poll_source", next_run_time=None,
        )
    scheduler.start()
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="Equipment Document Intelligence POC", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/health")
def health():
    return {"status": "ok"}


# --- Serialization helpers -------------------------------------------------- #

def _equipment_dict(eq: Equipment, db: Session) -> dict:
    d = status.days_until_due(eq, db)
    return {
        "id": eq.id,
        "equipment_code": eq.equipment_code,
        "name": eq.name,
        "category": eq.category,
        "manufacture_date": eq.manufacture_date.isoformat() if eq.manufacture_date else None,
        "service_interval_days": eq.service_interval_days,
        "last_service_date": eq.last_service_date.isoformat() if eq.last_service_date else None,
        "status": eq.status,
        "current_state": eq.current_state,
        "notes": eq.notes,
        "days_until_due": d,
    }


def _status_explanation(eq: Equipment, db: Session) -> str:
    d = status.days_until_due(eq, db)
    if eq.current_state == "in_service":
        return "Red: unit is in service and requires attention."
    if d is None:
        return f"Green: no service due date on record; state is {eq.current_state}."
    if d < 0:
        return f"Red: service overdue by {abs(d)} days."
    if d <= 30:
        return f"Orange: service due in {d} days."
    return f"Green: service due in {d} days; state is {eq.current_state}."


# --- Ingestion -------------------------------------------------------------- #

@app.post("/documents/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF uploads are supported.")
    pdf_bytes = await file.read()

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe = f"{uuid.uuid4().hex}_{os.path.basename(file.filename)}"
    dest = os.path.join(UPLOAD_DIR, safe)
    with open(dest, "wb") as f:
        f.write(pdf_bytes)

    try:
        result = ingest_pdf(db, filename=file.filename, pdf_bytes=pdf_bytes, file_path=dest)
    except Exception as e:  # extraction must degrade gracefully, never 500 hard
        db.rollback()
        raise HTTPException(502, f"Extraction pipeline error: {e}")
    db.commit()
    return result


# --- Portal reads ----------------------------------------------------------- #

@app.get("/equipment")
def list_equipment(db: Session = Depends(get_db)):
    rows = db.execute(select(Equipment).order_by(Equipment.equipment_code)).scalars().all()
    items = [_equipment_dict(eq, db) for eq in rows]
    summary = {"green": 0, "orange": 0, "red": 0}
    for it in items:
        summary[it["status"]] = summary.get(it["status"], 0) + 1
    return {"summary": summary, "count": len(items), "equipment": items}


@app.get("/equipment/{equipment_id}")
def get_equipment(equipment_id: int, db: Session = Depends(get_db)):
    eq = db.get(Equipment, equipment_id)
    if eq is None:
        raise HTTPException(404, "Equipment not found")

    txns = db.execute(
        select(Transaction).where(Transaction.equipment_id == eq.id)
        .order_by(Transaction.transaction_date.desc().nullslast(), Transaction.id.desc())
    ).scalars().all()
    svcs = db.execute(
        select(ServiceRecord).where(ServiceRecord.equipment_id == eq.id)
        .order_by(ServiceRecord.service_date.desc().nullslast(), ServiceRecord.id.desc())
    ).scalars().all()
    notes = db.execute(
        select(Notification).where(Notification.equipment_id == eq.id)
        .order_by(Notification.sent_at.desc())
    ).scalars().all()

    # Linked source documents (via transactions + service records).
    doc_ids = {t.document_id for t in txns} | {s.document_id for s in svcs}
    docs = []
    if doc_ids:
        docs = db.execute(
            select(Document).where(Document.id.in_(doc_ids))
            .order_by(Document.uploaded_at.desc())
        ).scalars().all()

    return {
        **_equipment_dict(eq, db),
        "status_explanation": _status_explanation(eq, db),
        "transactions": [
            {"id": t.id, "document_id": t.document_id, "type": t.type,
             "customer_name": t.customer_name,
             "transaction_date": t.transaction_date.isoformat() if t.transaction_date else None,
             "due_back_date": t.due_back_date.isoformat() if t.due_back_date else None,
             "amount": t.amount, "currency": t.currency}
            for t in txns
        ],
        "service_records": [
            {"id": s.id, "document_id": s.document_id,
             "service_date": s.service_date.isoformat() if s.service_date else None,
             "service_type": s.service_type, "technician": s.technician,
             "next_due_date": s.next_due_date.isoformat() if s.next_due_date else None,
             "findings": s.findings}
            for s in svcs
        ],
        "documents": [
            {"id": d.id, "filename": d.filename, "doc_type": d.doc_type,
             "needs_review": d.needs_review,
             "extraction_confidence": d.extraction_confidence}
            for d in docs
        ],
        "notifications": [
            {"id": n.id, "channel": n.channel, "message": n.message, "level": n.level,
             "sent_at": n.sent_at.isoformat()}
            for n in notes
        ],
    }


@app.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    rows = db.execute(select(Document).order_by(Document.uploaded_at.desc())).scalars().all()
    return [
        {"id": d.id, "filename": d.filename, "doc_type": d.doc_type,
         "uploaded_at": d.uploaded_at.isoformat(),
         "extraction_confidence": d.extraction_confidence,
         "needs_review": d.needs_review}
        for d in rows
    ]


@app.get("/documents/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(404, "Document not found")
    return {
        "id": d.id, "filename": d.filename, "doc_type": d.doc_type,
        "uploaded_at": d.uploaded_at.isoformat(), "file_path": d.file_path,
        "extraction_confidence": d.extraction_confidence,
        "needs_review": d.needs_review,
        "raw_extraction_json": d.raw_extraction_json,
    }


@app.get("/documents/{document_id}/file")
def get_document_file(document_id: int, db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if d is None or not d.file_path or not os.path.exists(d.file_path):
        raise HTTPException(404, "Source file not available")
    return FileResponse(d.file_path, media_type="application/pdf", filename=d.filename)


@app.get("/review-queue")
def review_queue(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Document).where(Document.needs_review == True)  # noqa: E712
        .order_by(Document.uploaded_at.desc())
    ).scalars().all()
    return [
        {"id": d.id, "filename": d.filename, "doc_type": d.doc_type,
         "extraction_confidence": d.extraction_confidence,
         "raw_extraction_json": d.raw_extraction_json,
         "uploaded_at": d.uploaded_at.isoformat()}
        for d in rows
    ]


class EquipmentPatch(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    service_interval_days: Optional[int] = None
    current_state: Optional[str] = None


class ApproveBody(BaseModel):
    equipment_id: Optional[int] = None
    equipment_patch: Optional[EquipmentPatch] = None


@app.post("/documents/{document_id}/approve")
def approve_document(document_id: int, body: ApproveBody, db: Session = Depends(get_db)):
    d = db.get(Document, document_id)
    if d is None:
        raise HTTPException(404, "Document not found")
    if body.equipment_id and body.equipment_patch:
        eq = db.get(Equipment, body.equipment_id)
        if eq is None:
            raise HTTPException(404, "Equipment not found")
        patch = body.equipment_patch
        for field_name in ("name", "category", "service_interval_days", "current_state"):
            val = getattr(patch, field_name)
            if val is not None:
                setattr(eq, field_name, val)
    d.needs_review = False
    db.flush()
    recompute_and_notify(db)  # corrections may change status
    return {"id": d.id, "needs_review": d.needs_review}


@app.get("/notifications")
def list_notifications(db: Session = Depends(get_db)):
    rows = db.execute(
        select(Notification).where(Notification.channel == "in_app")
        .order_by(Notification.sent_at.desc())
    ).scalars().all()
    return [
        {"id": n.id, "equipment_id": n.equipment_id, "channel": n.channel,
         "message": n.message, "level": n.level, "sent_at": n.sent_at.isoformat()}
        for n in rows
    ]


class RecomputeBody(BaseModel):
    ref_date: Optional[date] = None  # override "today" for stage demos


@app.post("/admin/recompute")
def admin_recompute(body: RecomputeBody = RecomputeBody(), db: Session = Depends(get_db)):
    changes = recompute_and_notify(db, body.ref_date)
    return {"changed": changes}


@app.post("/admin/ingest-now")
def admin_ingest_now(db: Session = Depends(get_db)):
    """Scan the configured source (OneDrive folder / local inbox) on demand and
    ingest any new PDFs. Idempotent — already-seen files are skipped."""
    return source.scan_and_ingest(db)
