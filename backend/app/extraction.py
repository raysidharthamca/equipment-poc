"""Claude-powered classification + extraction pipeline (Phase 3).

Two-step design:
  1. classify() -> {doc_type, confidence}
  2. extract()  -> doc-type-specific structured JSON, validated against the
                   matching Pydantic schema.

Degradation rules (never crash, never silently drop):
  - Validation failure -> retry once with the error appended to the prompt.
  - Second failure     -> store raw text, needs_review = True.
  - Confidence < 0.8   -> record still saved, but needs_review = True.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Optional

import anthropic
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.schemas import EXTRACTION_SCHEMAS, Classification

# Extraction is a high-volume, latency-sensitive classification task, so the
# model defaults to Haiku 4.5 (fast + cheap). Configurable via ANTHROPIC_MODEL.
MODEL = settings.ANTHROPIC_MODEL
CONFIDENCE_REVIEW_THRESHOLD = 0.8

ALLOWED_DOC_TYPES = list(EXTRACTION_SCHEMAS.keys()) + ["unknown"]


@dataclass
class ExtractionResult:
    doc_type: str
    confidence: float
    needs_review: bool
    data: Optional[BaseModel]  # validated model, or None if it fell to review
    raw_json: str  # raw model text (for audit / review queue)
    review_reason: Optional[str] = None


_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set — copy .env.example to .env and add your key."
            )
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _pdf_block(pdf_bytes: bytes) -> dict:
    b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": b64},
    }


def _ask(pdf_bytes: bytes, prompt: str) -> str:
    """Single JSON-only call. Returns the raw text content."""
    client = _get_client()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        thinking={"type": "disabled"},  # extraction is mechanical; keep it fast
        messages=[
            {
                "role": "user",
                "content": [_pdf_block(pdf_bytes), {"type": "text", "text": prompt}],
            }
        ],
    )
    parts = [b.text for b in resp.content if b.type == "text"]
    return "".join(parts).strip()


def _strip_fences(text: str) -> str:
    """Defensive: strip accidental ```json fences even though we ask for none."""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


# --- Step 1: classify ------------------------------------------------------- #

CLASSIFY_PROMPT = f"""You are an oil & gas equipment document classifier.
Classify this PDF into exactly one document type from this list:
{", ".join(ALLOWED_DOC_TYPES)}

Respond with JSON ONLY (no markdown fences, no prose):
{{"doc_type": "<one of the allowed types>", "confidence": <number 0.0-1.0>}}
Use "unknown" if it fits none. confidence reflects how sure you are of the type."""


def classify(pdf_bytes: bytes) -> Classification:
    text = _strip_fences(_ask(pdf_bytes, CLASSIFY_PROMPT))
    try:
        return Classification.model_validate_json(text)
    except (ValidationError, ValueError):
        # Never crash on a bad classification — treat as unknown, low confidence.
        return Classification(doc_type="unknown", confidence=0.0)


# --- Step 2: extract -------------------------------------------------------- #

def _extract_prompt(doc_type: str, schema: type[BaseModel]) -> str:
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    return f"""You are extracting structured data from an oil & gas
{doc_type.replace('_', ' ')} PDF.

Extract the fields described by this JSON Schema:
{schema_json}

Rules:
- Respond with JSON ONLY. No markdown fences, no explanation.
- Use null for any field that is missing or illegible.
- Format all dates as ISO YYYY-MM-DD.
- Equipment codes look like PMP-0041, CMP-0102, VLV-0210, ASM-0333.
- Include a top-level "confidence" between 0.0 and 1.0 reflecting how legible
  and unambiguous the source was. Lower it when fields are smudged, illegible,
  or handwritten."""


def extract(pdf_bytes: bytes, doc_type: str) -> ExtractionResult:
    schema = EXTRACTION_SCHEMAS.get(doc_type)
    if schema is None:
        # unknown doc type -> nothing structured to pull; goes to review.
        return ExtractionResult(
            doc_type="unknown",
            confidence=0.0,
            needs_review=True,
            data=None,
            raw_json="",
            review_reason="Unrecognized document type",
        )

    prompt = _extract_prompt(doc_type, schema)
    raw = _strip_fences(_ask(pdf_bytes, prompt))

    # First validation attempt.
    model, err = _validate(schema, raw)
    if model is None:
        # Retry once with the validation error appended.
        retry_prompt = (
            prompt
            + f"\n\nYour previous response failed validation with:\n{err}\n"
            + "Return corrected JSON only."
        )
        raw = _strip_fences(_ask(pdf_bytes, retry_prompt))
        model, err = _validate(schema, raw)

    if model is None:
        return ExtractionResult(
            doc_type=doc_type,
            confidence=0.0,
            needs_review=True,
            data=None,
            raw_json=raw,
            review_reason=f"Validation failed after retry: {err}",
        )

    confidence = float(getattr(model, "confidence", 1.0) or 0.0)
    needs_review = confidence < CONFIDENCE_REVIEW_THRESHOLD
    reason = (
        f"Low extraction confidence ({confidence:.2f})" if needs_review else None
    )
    return ExtractionResult(
        doc_type=doc_type,
        confidence=confidence,
        needs_review=needs_review,
        data=model,
        raw_json=raw,
        review_reason=reason,
    )


def _validate(schema: type[BaseModel], raw: str):
    try:
        return schema.model_validate_json(raw), None
    except ValidationError as e:
        return None, str(e)
    except ValueError as e:  # invalid JSON
        return None, f"Invalid JSON: {e}"


# --- Orchestration ---------------------------------------------------------- #

def run_pipeline(pdf_bytes: bytes) -> ExtractionResult:
    """Full classify -> extract pass over a single PDF."""
    cls = classify(pdf_bytes)
    result = extract(pdf_bytes, cls.doc_type)
    # A confident extraction shouldn't be undermined by a shaky classification,
    # but a very unsure classification is itself a review signal.
    if cls.confidence < CONFIDENCE_REVIEW_THRESHOLD and not result.needs_review:
        result.needs_review = True
        result.review_reason = f"Low classification confidence ({cls.confidence:.2f})"
    return result
