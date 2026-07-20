"""Live extraction tests — these hit the real Claude API and are SKIPPED unless
ANTHROPIC_API_KEY is set (via env or backend/.env).

Run just these after adding your key:
    .venv/bin/pytest -m live -v
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.extraction import run_pipeline
from app.ingest import ingest_pdf
from app.models import Equipment

from .canned import REF

SAMPLES = Path(__file__).resolve().parent.parent / "sample_docs"

# Gate the whole module on a real key. settings reads env + .env at import, so
# this works whether the key is exported or lives in backend/.env.
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not settings.ANTHROPIC_API_KEY,
        reason="set ANTHROPIC_API_KEY (env or backend/.env) to run live extraction tests",
    ),
]


def _pdf(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


def test_classifies_and_extracts_purchase_order():
    result = run_pipeline(_pdf("po_2026_0012_permian_sale.pdf"))
    assert result.doc_type == "purchase_order"
    assert result.data is not None
    assert result.data.customer_name  # extracted something meaningful
    codes = {li.equipment_code for li in result.data.line_items}
    assert "PMP-0041" in codes
    assert 0.0 <= result.confidence <= 1.0


def test_classifies_and_extracts_service_record():
    result = run_pipeline(_pdf("sr_2026_0051_pmp0041_green.pdf"))
    assert result.doc_type == "service_record"
    assert result.data is not None
    assert result.data.equipment_code == "PMP-0041"


def test_messy_record_lands_in_review_or_low_confidence():
    """The illegible-technician slip should extract but with lower confidence /
    a review flag (exact confidence is model-dependent, so assert leniently)."""
    result = run_pipeline(_pdf("sr_2026_0055_vlv0210_red.pdf"))
    assert result.doc_type == "service_record"
    assert result.data is not None
    assert result.data.equipment_code == "VLV-0210"
    assert result.needs_review or result.confidence < 1.0


def test_live_end_to_end_ingest_creates_equipment(db):
    """Spec sheet + service record through the real pipeline -> a green pump."""
    for name in ("spec_pmp_0041.pdf", "sr_2026_0051_pmp0041_green.pdf"):
        ingest_pdf(db, filename=name, pdf_bytes=_pdf(name),
                   source_id=name, ref_date=REF)
        db.commit()
    pump = db.execute(
        select(Equipment).where(Equipment.equipment_code == "PMP-0041")
    ).scalars().first()
    assert pump is not None
    assert pump.status in ("green", "orange", "red")
