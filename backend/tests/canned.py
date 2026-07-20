"""Canned extraction results that mirror the sample PDFs, plus a fake
run_pipeline for mocking the Claude call in tests.

These let the ingest/status/notify/source pipeline be tested end-to-end without
an API key. The `live` tests (test_extraction_live.py) exercise the real thing.
"""
from __future__ import annotations

from datetime import date

from app.extraction import ExtractionResult
from app.schemas import (
    LineItem,
    PurchaseOrderExtract,
    RentalContractExtract,
    ReturnRecordExtract,
    ServiceRecordExtract,
    SpecSheetExtract,
)

# Fixed reference "today" so day-count assertions are deterministic.
REF = date(2026, 7, 16)

CANNED: dict[str, ExtractionResult] = {
    "spec_pmp_0041.pdf": ExtractionResult(
        "spec_sheet", 0.98, False,
        SpecSheetExtract(equipment_code="PMP-0041", name="Centrifugal Pump 6x4x13",
                         category="pump", service_interval_days=180,
                         specs={"Rated Flow": "1200 GPM"}, confidence=0.98), "{}"),
    "po_2026_0012_permian_sale.pdf": ExtractionResult(
        "purchase_order", 0.96, False,
        PurchaseOrderExtract(po_number="PO-2026-0012", customer_name="Permian Basin Drilling LLC",
                             order_date=date(2026, 2, 3),
                             line_items=[LineItem(equipment_code="PMP-0041", description="Centrifugal Pump", qty=1, unit_price=42000),
                                         LineItem(equipment_code="VLV-0210", description="Gate Valve", qty=2, unit_price=3150)],
                             total=48300, currency="USD", is_sale=True, confidence=0.96), "{}"),
    "po_2026_0018_gulfcoast.pdf": ExtractionResult(
        "purchase_order", 0.95, False,
        PurchaseOrderExtract(po_number="PO-2026-0018", customer_name="Gulf Coast Energy Services",
                             order_date=date(2026, 4, 18),
                             line_items=[LineItem(equipment_code="CMP-0102", description="Reciprocating Compressor", qty=1, unit_price=88500),
                                         LineItem(equipment_code="CMP-0103", description="Rotary Screw Compressor", qty=1, unit_price=61250)],
                             total=149750, currency="USD", is_sale=True, confidence=0.95), "{}"),
    "po_2026_0021_anadarko.pdf": ExtractionResult(
        "purchase_order", 0.94, False,
        PurchaseOrderExtract(po_number="PO-2026-0021", customer_name="Anadarko Field Operations",
                             order_date=date(2026, 5, 27),
                             line_items=[LineItem(equipment_code="VLV-0211", description="Ball Valve", qty=4, unit_price=1875),
                                         LineItem(equipment_code="PMP-0042", description="Centrifugal Pump", qty=1, unit_price=36900)],
                             total=44400, currency="USD", is_sale=True, confidence=0.94), "{}"),
    "rc_2026_0007_westtexas.pdf": ExtractionResult(
        "rental_contract", 0.95, False,
        RentalContractExtract(contract_number="RC-2026-0007", customer_name="West Texas Wireline Inc.",
                              start_date=date(2026, 6, 20), due_back_date=date(2026, 7, 20),
                              equipment_codes=["ASM-0333"], monthly_rate=4200, currency="USD", confidence=0.95), "{}"),
    "rc_2026_0009_bakken.pdf": ExtractionResult(
        "rental_contract", 0.93, False,
        RentalContractExtract(contract_number="RC-2026-0009", customer_name="Bakken Drilling Partners",
                              start_date=date(2026, 5, 1), due_back_date=date(2026, 9, 1),
                              equipment_codes=["CMP-0103"], monthly_rate=2750, currency="USD", confidence=0.93), "{}"),
    "rr_2026_0003_return.pdf": ExtractionResult(
        "return_record", 0.90, False,
        ReturnRecordExtract(contract_number="RC-2026-0009", equipment_codes=["CMP-0103"],
                            return_date=date(2026, 6, 28), condition_notes="Minor corrosion", confidence=0.90), "{}"),
    "sr_2026_0051_pmp0041_green.pdf": ExtractionResult(
        "service_record", 0.97, False,
        ServiceRecordExtract(equipment_code="PMP-0041", service_date=date(2026, 7, 1),
                             service_type="180-Day PM", technician="J. Alvarez",
                             next_due_date=date(2026, 12, 28), findings="Seals replaced", confidence=0.97), "{}"),
    "sr_2026_0052_cmp0102_orange.pdf": ExtractionResult(
        "service_record", 0.94, False,
        ServiceRecordExtract(equipment_code="CMP-0102", service_date=date(2026, 2, 10),
                             service_type="Semi-Annual PM", technician="R. Delgado",
                             next_due_date=date(2026, 8, 9), findings="Valve clearances adjusted", confidence=0.94), "{}"),
    # Messy record -> low confidence -> review queue; illegible technician.
    "sr_2026_0055_vlv0210_red.pdf": ExtractionResult(
        "service_record", 0.55, True,
        ServiceRecordExtract(equipment_code="VLV-0210", service_date=date(2025, 12, 1),
                             service_type="leak-test / seat lap", technician=None,
                             next_due_date=date(2026, 5, 30), findings="Seat pitting; overdue", confidence=0.55),
        "{}", review_reason="Low extraction confidence (0.55)"),
}

# Lifecycle order (spec -> sales -> rentals -> returns -> service records).
ORDER = list(CANNED.keys())


def make_filename_keyed_run():
    """A fake run_pipeline that returns the canned result for whichever file is
    'current'. Set `.current` before each ingest call."""
    def fake_run(pdf_bytes):
        return CANNED[fake_run.current]
    fake_run.current = ORDER[0]
    return fake_run


def make_fixed_run(result: ExtractionResult):
    """A fake run_pipeline that returns the same result for every PDF (used by
    source-scanner tests where content doesn't matter, only dedupe)."""
    def fake_run(pdf_bytes):
        return result
    return fake_run
