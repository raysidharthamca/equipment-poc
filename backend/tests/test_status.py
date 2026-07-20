"""Phase 4 — status engine thresholds (pure logic, mocked data)."""
from __future__ import annotations

from datetime import date

from app import status
from app.models import Document, Equipment, ServiceRecord

REF = date(2026, 7, 16)


def _equipment(db, next_due=None, *, state="available", interval=180, last=None):
    """Create an equipment (optionally with a service record carrying a
    next_due_date) and return it."""
    n = db.query(Equipment).count() + 1
    eq = Equipment(equipment_code=f"T-{n:04d}", status="green",
                   current_state=state, service_interval_days=interval,
                   last_service_date=last)
    db.add(eq)
    db.flush()
    if next_due is not None:
        doc = Document(filename="x.pdf", doc_type="service_record")
        db.add(doc)
        db.flush()
        db.add(ServiceRecord(equipment_id=eq.id, document_id=doc.id,
                             service_date=date(2026, 1, 1), next_due_date=next_due))
        db.flush()
    return eq


def test_green_due_far_out(db):
    eq = _equipment(db, date(2026, 9, 14))  # ~60 days out
    assert status.compute_status(eq, db, REF) == "green"


def test_orange_due_in_30_days(db):
    eq = _equipment(db, date(2026, 8, 15))  # exactly 30 days
    assert status.compute_status(eq, db, REF) == "orange"


def test_orange_due_today(db):
    eq = _equipment(db, REF)  # 0 days
    assert status.compute_status(eq, db, REF) == "orange"


def test_red_overdue(db):
    eq = _equipment(db, date(2026, 7, 4))  # 12 days overdue
    assert status.compute_status(eq, db, REF) == "red"


def test_red_in_service_regardless_of_due(db):
    eq = _equipment(db, date(2026, 12, 1), state="in_service")
    assert status.compute_status(eq, db, REF) == "red"


def test_green_when_no_service_info(db):
    eq = _equipment(db, None)
    assert status.compute_status(eq, db, REF) == "green"


def test_days_until_due_interval_fallback(db):
    eq = _equipment(db, None, last=date(2026, 6, 1))  # 2026-06-01 + 180 days
    expected = (date(2026, 6, 1) - REF).days + 180
    assert status.days_until_due(eq, db, REF) == expected
