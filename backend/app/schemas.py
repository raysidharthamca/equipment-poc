"""Pydantic schemas for API I/O and Claude extraction (Phase 3).

Extraction schemas are one-per-doc-type. The extraction pipeline validates
Claude's JSON against the matching schema; on failure it retries once, then
falls back to the review queue.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Allowed document types (mirror models.Document.doc_type vocabulary).
DocType = Literal[
    "purchase_order",
    "rental_contract",
    "service_record",
    "return_record",
    "spec_sheet",
    "unknown",
]


# --- Classification (step 1) ------------------------------------------------ #

class Classification(BaseModel):
    doc_type: DocType
    confidence: float = Field(ge=0.0, le=1.0)


# --- Extraction schemas (step 2), one per doc type -------------------------- #

class LineItem(BaseModel):
    equipment_code: Optional[str] = None
    description: Optional[str] = None
    qty: Optional[float] = None
    unit_price: Optional[float] = None


class PurchaseOrderExtract(BaseModel):
    po_number: Optional[str] = None
    customer_name: Optional[str] = None
    order_date: Optional[date] = None
    line_items: list[LineItem] = Field(default_factory=list)
    total: Optional[float] = None
    currency: Optional[str] = None
    # True when the PO transfers ownership (sale) vs. an inbound purchase.
    is_sale: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class RentalContractExtract(BaseModel):
    contract_number: Optional[str] = None
    customer_name: Optional[str] = None
    start_date: Optional[date] = None
    due_back_date: Optional[date] = None
    equipment_codes: list[str] = Field(default_factory=list)
    monthly_rate: Optional[float] = None
    currency: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ServiceRecordExtract(BaseModel):
    equipment_code: Optional[str] = None
    service_date: Optional[date] = None
    service_type: Optional[str] = None
    technician: Optional[str] = None
    next_due_date: Optional[date] = None
    findings: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ReturnRecordExtract(BaseModel):
    contract_number: Optional[str] = None
    equipment_codes: list[str] = Field(default_factory=list)
    return_date: Optional[date] = None
    condition_notes: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SpecSheetExtract(BaseModel):
    equipment_code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    service_interval_days: Optional[int] = None
    specs: dict = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


# Map doc_type -> extraction schema. `unknown`/`spec_sheet` handled specially.
EXTRACTION_SCHEMAS: dict[str, type[BaseModel]] = {
    "purchase_order": PurchaseOrderExtract,
    "rental_contract": RentalContractExtract,
    "service_record": ServiceRecordExtract,
    "return_record": ReturnRecordExtract,
    "spec_sheet": SpecSheetExtract,
}


# --- API response schemas (portal) ------------------------------------------ #

class EquipmentOut(BaseModel):
    id: int
    equipment_code: str
    name: Optional[str] = None
    category: Optional[str] = None
    manufacture_date: Optional[date] = None
    service_interval_days: int
    last_service_date: Optional[date] = None
    status: str
    current_state: str
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: int
    filename: str
    doc_type: str
    uploaded_at: datetime
    file_path: Optional[str] = None
    extraction_confidence: Optional[float] = None
    needs_review: bool

    model_config = ConfigDict(from_attributes=True)


class TransactionOut(BaseModel):
    id: int
    equipment_id: int
    document_id: int
    type: str
    customer_name: Optional[str] = None
    transaction_date: Optional[date] = None
    due_back_date: Optional[date] = None
    amount: Optional[float] = None
    currency: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ServiceRecordOut(BaseModel):
    id: int
    equipment_id: int
    document_id: int
    service_date: Optional[date] = None
    service_type: Optional[str] = None
    technician: Optional[str] = None
    next_due_date: Optional[date] = None
    findings: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseModel):
    id: int
    equipment_id: int
    channel: str
    message: str
    sent_at: datetime
    level: str

    model_config = ConfigDict(from_attributes=True)
