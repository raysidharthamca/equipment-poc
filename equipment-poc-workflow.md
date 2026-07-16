---
name: equipment-poc-builder
description: "Step-by-step workflow for building a POC of an oil & gas equipment
  document-intelligence system: PDF ingestion, Claude-powered extraction to a
  database, service-due status logic (green/orange/red), Teams/email alerts, and
  a React portal. Use when the user says 'build the equipment POC', 'equipment
  tracker demo', 'document extraction POC', or asks to implement any phase of
  this system."
---

# Equipment Document Intelligence POC — Build Workflow

This workflow builds a vendor-side demo of an equipment lifecycle tracking
system. PDFs (purchase orders, rental contracts, service records, returns) are
uploaded, Claude extracts structured data, records land in a database, a status
engine computes green/orange/red per equipment, alerts fire to Teams/email, and
a web portal displays everything.

Follow the phases in order. Each phase ends with a verification step — do not
move on until it passes. Ask the user before any step marked **[CONFIRM]**.

---

## Target Architecture

```
[Upload UI / OneDrive folder]
        │  PDF
        ▼
[FastAPI backend] ──► [Claude API: classify + extract → JSON]
        │                       │
        ▼                       ▼
[SQLite / Postgres] ◄── validated records + link to source PDF
        │
        ├──► [Status engine (daily job + on-write): green / orange / red]
        │           │
        │           └──► [Teams incoming webhook + email alert]
        ▼
[React portal: equipment cards, status colors, detail view, notification feed]
```

## Tech Stack (POC tier)

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.11+, FastAPI, uvicorn | single service |
| Extraction | Claude API (`claude-sonnet-4-6`) | PDF as base64 document block |
| Database | SQLite via SQLAlchemy | swap to Postgres/Supabase later, no code change |
| Frontend | React + Vite, Tailwind | deploy to Vercel for live demo |
| Alerts | Teams incoming webhook + SMTP/Resend | plus in-app notification feed fallback |
| Sample data | 8–10 generated PDFs | reportlab or HTML→PDF |

Environment variables (put in `.env`, never commit):
`ANTHROPIC_API_KEY`, `TEAMS_WEBHOOK_URL` (optional), `SMTP_*` or
`RESEND_API_KEY` (optional), `DATABASE_URL` (default `sqlite:///./poc.db`).

---

## Phase 0 — Project Scaffold

1. Create the repo layout:

```
equipment-poc/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + routes
│   │   ├── models.py          # SQLAlchemy models
│   │   ├── schemas.py         # Pydantic schemas (incl. extraction schemas)
│   │   ├── extraction.py      # Claude classify + extract
│   │   ├── status.py          # green/orange/red engine
│   │   ├── notify.py          # Teams + email senders
│   │   └── seed.py            # load sample PDFs through the real pipeline
│   ├── sample_docs/           # generated demo PDFs
│   ├── generate_samples.py
│   ├── requirements.txt
│   └── .env.example
└── frontend/                  # Vite React app
```

2. `requirements.txt`: fastapi, uvicorn, sqlalchemy, pydantic, anthropic,
   python-multipart, reportlab, httpx, python-dotenv, apscheduler.
3. Verify: `uvicorn app.main:app` serves a `/health` endpoint returning
   `{"status": "ok"}`.

---

## Phase 1 — Database Schema

Create SQLAlchemy models in `models.py`:

**equipment**
- id (PK), equipment_code (unique, e.g. "PMP-0041"), name, category
  (pump/compressor/valve/assembly), manufacture_date, service_interval_days
  (int, default 180), last_service_date, status (green/orange/red, computed),
  current_state (available / rented / sold / in_service), notes

**documents**
- id (PK), filename, doc_type (purchase_order / rental_contract /
  service_record / return_record / spec_sheet / unknown), uploaded_at,
  file_path, extraction_confidence (float 0–1), raw_extraction_json (text),
  needs_review (bool)

**transactions**
- id (PK), equipment_id (FK), document_id (FK), type (sale / rental_start /
  rental_return), customer_name, transaction_date, due_back_date (nullable),
  amount (nullable), currency

**service_records**
- id (PK), equipment_id (FK), document_id (FK), service_date, service_type,
  technician, next_due_date (nullable), findings

**notifications**
- id (PK), equipment_id (FK), channel (teams / email / in_app), message,
  sent_at, level (warning / critical)

Rules:
- Every extracted record must link back to its source document row.
- Unknown equipment codes in a document create a new equipment row flagged
  `needs_review = true` on the document.

Verify: tables create cleanly on startup; insert + query one row of each.

---

## Phase 2 — Sample Document Generation

Write `generate_samples.py` producing realistic PDFs into `sample_docs/`:

- 3 purchase orders (different customers, one selling equipment outright)
- 2 rental contracts (with start date and due-back date)
- 1 rental return record
- 3 service records (one recent → green; one ~5 months old with 180-day
  interval → orange; one overdue → red)
- 1 equipment spec sheet (nitty-gritty specs: pressure rating, materials,
  assembly parts list)

Requirements:
- Consistent equipment codes across documents so the demo shows lifecycle
  (e.g. PMP-0041 appears in a PO, a service record, and a rental contract).
- Realistic layout: company header, tables, signature lines — not plain text —
  so the extraction demo looks credible.
- Vary layouts between documents of the same type to prove the LLM handles
  format drift (this is the selling point vs. template-based OCR).

Verify: open each PDF, confirm human-readable and data-consistent.

---

## Phase 3 — Claude Extraction Pipeline

Implement `extraction.py` as a two-step call:

**Step 1 — Classify.** Send the PDF (base64 document block) with a prompt
asking only for the doc_type from the allowed list plus a confidence 0–1.
Force JSON-only output.

**Step 2 — Extract.** Based on doc_type, send the PDF again with the matching
extraction schema. Define one Pydantic schema per doc type in `schemas.py`,
e.g.:

- PurchaseOrderExtract: po_number, customer_name, order_date, line_items
  [{equipment_code, description, qty, unit_price}], total, currency
- RentalContractExtract: contract_number, customer_name, start_date,
  due_back_date, equipment_codes, monthly_rate
- ServiceRecordExtract: equipment_code, service_date, service_type,
  technician, next_due_date, findings
- ReturnRecordExtract: contract_number, equipment_codes, return_date,
  condition_notes

Prompt rules:
- Instruct: respond with JSON only, no markdown fences, use `null` for
  missing fields, dates as ISO `YYYY-MM-DD`, include a top-level
  `confidence` 0–1.
- Validate the response against the Pydantic schema. On validation failure,
  retry once with the validation error appended to the prompt. On second
  failure, store the raw text and set `needs_review = true`.
- Confidence < 0.8 → `needs_review = true` (record still saved).

Wire the pipeline into a FastAPI route: `POST /documents/upload` →
save file → classify → extract → validate → write documents +
transactions/service_records rows → update equipment → recompute status →
trigger notifications if status worsened → return the full result JSON.

Verify: run all sample PDFs through the endpoint; every one produces correct
rows; at least one deliberately messy field lands in the review queue.

---

## Phase 4 — Status Engine

Implement `status.py`:

```
days_until_due = (last_service_date + service_interval_days) - today
  (use next_due_date from the latest service record when present)

GREEN  : days_until_due > 30 and current_state == available
ORANGE : 0 <= days_until_due <= 30
RED    : days_until_due < 0 (overdue) or current_state == in_service
```

State transitions from documents:
- purchase order (sale) → current_state = sold
- rental contract → rented (store due_back_date)
- return record → available, trigger status recompute
- service record → last_service_date updated, usually flips to green

Run the engine: (a) after every document write, and (b) on a daily
APScheduler job (for the demo, also expose `POST /admin/recompute` to force
it live on stage).

Verify: unit-test the three thresholds and the overdue path; confirm the
seeded data produces at least one of each color.

---

## Phase 5 — Notifications

Implement `notify.py`:

- **Teams:** POST an Adaptive Card to `TEAMS_WEBHOOK_URL` — equipment code,
  name, status color, days overdue/remaining, deep link to the portal detail
  page. Skip silently if the env var is unset.
- **Email:** simple HTML mail via SMTP or Resend with the same content.
  Optional like Teams.
- **In-app feed:** always write a notifications row — the portal renders
  these, so the demo works even with no webhook configured.

Trigger rules: fire when a status transitions to orange (level=warning) or
red (level=critical), and when a rental due_back_date is within 7 days.
Never re-fire for the same equipment+level within 24h (dedupe check).

Verify: flip a seeded equipment to orange via `/admin/recompute` with a
backdated service date; confirm Teams card (if configured) and feed row.

---

## Phase 6 — React Portal

Build in `frontend/` with Vite + React + Tailwind:

**Pages**
1. **Dashboard** — grid of equipment cards: code, name, category, big status
   dot (green/orange/red), current_state badge, days-until-service. Filters:
   status, category, state. Summary bar: counts per color.
2. **Equipment detail** — full spec fields, transaction history timeline,
   service history, linked source PDFs (open original), status explanation
   ("Red: service overdue by 12 days").
3. **Upload** — drag-and-drop PDF → shows live extraction progress → renders
   the extracted JSON as a review form → save. This is the demo centerpiece.
4. **Review queue** — documents with needs_review = true; editable fields;
   approve button writes corrections.
5. **Notification feed** — reverse-chron list of alerts with level colors.

**Rules**
- Status colors must be unmistakable at projector distance (large dots,
  colored card borders).
- Poll or use a websocket so a status flip appears without manual refresh —
  the "card turns green live" moment is the pitch.
- Keep the API base URL in one config constant for easy deploy switching.

Verify: full loop — upload the service-record PDF for a red equipment →
extraction appears → card flips to green → notification feed updates.

---

## Phase 7 — Seed + Demo Script

1. `seed.py`: wipe DB, run every sample PDF through the real upload endpoint
   (not direct inserts — the demo data must come from the actual pipeline).
2. Write `DEMO.md` with the 5-minute script:
   - Open dashboard: mixed green/orange/red fleet
   - Tell the business story: "this red pump would have lost you the rental"
   - Live upload a new service record → watch extraction → card flips green →
     Teams alert pops on phone
   - Show detail page: every field traces to a source PDF (auditability)
   - Show review queue: "low-confidence extractions get a human check"
   - Close with the one-slide migration map: upload→Graph webhook,
     Claude→stays or Azure OpenAI, SQLite→Azure SQL, Vercel→App Service
3. **[CONFIRM]** Deploy: frontend to Vercel, backend to Railway/Render free
   tier, or run both locally for an in-person demo.

---

## Hard Rules

- Never commit `.env` or API keys; ship `.env.example` only.
- Every stored record must reference its source document (auditability is a
  selling point).
- Extraction must degrade gracefully: validation failure → review queue,
  never a crash or silent drop.
- All dates ISO `YYYY-MM-DD`; assume UTC in the POC.
- Keep total build scoped to a weekend: no auth, no multi-tenant, no OneDrive
  integration in the POC — those go on the migration slide, not in the code.
