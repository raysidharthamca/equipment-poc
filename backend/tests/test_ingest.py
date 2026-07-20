"""Phases 3(wiring)/4/5 — ingest the canned sample fleet through the real
persistence pipeline (extraction mocked) and assert the outcomes."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app import ingest as ingest_mod
from app.ingest import ingest_pdf
from app.models import Document, Equipment, Notification, ServiceRecord, Transaction

from .canned import ORDER, REF, make_filename_keyed_run


@pytest.fixture
def seeded(db, monkeypatch):
    """Ingest the full canned fleet in lifecycle order; return the session."""
    fake = make_filename_keyed_run()
    monkeypatch.setattr(ingest_mod, "run_pipeline", fake)
    for fn in ORDER:
        fake.current = fn
        ingest_pdf(db, filename=fn, pdf_bytes=b"", file_path=fn, source_id=fn, ref_date=REF)
        db.commit()
    return db


def _fleet(db):
    return {e.equipment_code: e for e in db.execute(select(Equipment)).scalars()}


def test_fleet_has_one_of_each_color(seeded):
    fleet = _fleet(seeded)
    colors = {c: [k for k, e in fleet.items() if e.status == c]
              for c in ("green", "orange", "red")}
    assert colors["green"] and colors["orange"] and colors["red"]


def test_specific_statuses(seeded):
    fleet = _fleet(seeded)
    assert fleet["PMP-0041"].status == "green"   # recent service
    assert fleet["CMP-0102"].status == "orange"  # due ~24 days
    assert fleet["VLV-0210"].status == "red"     # overdue


def test_state_transitions(seeded):
    fleet = _fleet(seeded)
    assert fleet["PMP-0041"].current_state == "sold"       # outright sale
    assert fleet["ASM-0333"].current_state == "rented"     # active rental
    assert fleet["CMP-0103"].current_state == "available"  # rented then returned


def test_every_record_links_to_source_document(seeded):
    txns = seeded.execute(select(Transaction)).scalars().all()
    svcs = seeded.execute(select(ServiceRecord)).scalars().all()
    assert txns and all(t.document_id is not None for t in txns)
    assert svcs and all(s.document_id is not None for s in svcs)


def test_review_queue_has_only_the_messy_record(seeded):
    review = seeded.execute(
        select(Document).where(Document.needs_review == True)  # noqa: E712
    ).scalars().all()
    assert [d.filename for d in review] == ["sr_2026_0055_vlv0210_red.pdf"]


def test_notifications_fire(seeded):
    feed = seeded.execute(
        select(Notification).where(Notification.channel == "in_app")
    ).scalars().all()
    levels = {n.level for n in feed}
    msgs = [n.message for n in feed]
    assert "critical" in levels   # VLV-0210 overdue
    assert "warning" in levels    # CMP-0102 due-soon / ASM-0333 due-back
    assert any("ASM-0333" in m and "return due" in m.lower() for m in msgs)


def test_notification_dedupe_within_24h(seeded):
    """A second identical status alert for the same equipment+level is deduped."""
    from app import notify
    eq = _fleet(seeded)["VLV-0210"]
    before = seeded.execute(select(Notification).where(
        Notification.equipment_id == eq.id, Notification.channel == "in_app")
    ).scalars().all()
    dup = notify.notify_status_change(seeded, eq, "red", -47)
    assert dup is None  # deduped
    after = seeded.execute(select(Notification).where(
        Notification.equipment_id == eq.id, Notification.channel == "in_app")
    ).scalars().all()
    assert len(after) == len(before)
