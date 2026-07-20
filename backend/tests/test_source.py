"""Ingestion source — local-folder scan picks up new PDFs and is idempotent
(re-scans skip already-ingested files by source_id). Extraction mocked."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import ingest as ingest_mod, source
from app.config import settings
from app.extraction import ExtractionResult
from app.models import Document
from app.schemas import SpecSheetExtract

from .canned import REF, make_fixed_run

SAMPLES = Path(__file__).resolve().parent.parent / "sample_docs"
SPEC = ExtractionResult(
    "spec_sheet", 0.95, False,
    SpecSheetExtract(equipment_code="PMP-0041", name="Pump", category="pump",
                     service_interval_days=180, confidence=0.95), "{}")


@pytest.fixture
def inbox(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "INGEST_SOURCE", "local")
    monkeypatch.setattr(settings, "LOCAL_INBOX_DIR", str(tmp_path))
    monkeypatch.setattr(ingest_mod, "run_pipeline", make_fixed_run(SPEC))
    return tmp_path


def _drop(inbox: Path, sample_name: str, as_name: str):
    shutil.copy(SAMPLES / sample_name, inbox / as_name)


def test_scan_ingests_new_files(db, inbox):
    _drop(inbox, "spec_pmp_0041.pdf", "a.pdf")
    _drop(inbox, "po_2026_0012_permian_sale.pdf", "b.pdf")
    summary = source.scan_and_ingest(db, ref_date=REF)
    assert len(summary["ingested"]) == 2
    assert summary["skipped"] == 0


def test_rescan_is_idempotent(db, inbox):
    _drop(inbox, "spec_pmp_0041.pdf", "a.pdf")
    source.scan_and_ingest(db, ref_date=REF)
    summary = source.scan_and_ingest(db, ref_date=REF)  # same folder again
    assert summary["ingested"] == []
    assert summary["skipped"] == 1


def test_new_file_after_rescan_is_picked_up(db, inbox):
    _drop(inbox, "spec_pmp_0041.pdf", "a.pdf")
    source.scan_and_ingest(db, ref_date=REF)
    _drop(inbox, "sr_2026_0051_pmp0041_green.pdf", "b.pdf")
    summary = source.scan_and_ingest(db, ref_date=REF)
    assert len(summary["ingested"]) == 1
    assert summary["skipped"] == 1


def test_every_document_has_source_id_and_servable_path(db, inbox):
    _drop(inbox, "spec_pmp_0041.pdf", "a.pdf")
    source.scan_and_ingest(db, ref_date=REF)
    docs = db.execute(select(Document)).scalars().all()
    assert docs
    for d in docs:
        assert d.source_id and d.source_id.startswith("local:")
        assert d.file_path and Path(d.file_path).exists()


def test_empty_inbox_ingests_nothing(db, inbox):
    summary = source.scan_and_ingest(db, ref_date=REF)
    assert summary["scanned"] == 0
    assert db.execute(select(func.count(Document.id))).scalar() == 0
