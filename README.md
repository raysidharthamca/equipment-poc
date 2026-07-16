# Equipment Document Intelligence POC

Vendor-side demo of an equipment lifecycle tracker. PDFs (purchase orders,
rental contracts, service records, returns, spec sheets) are uploaded, **Claude**
classifies and extracts structured data, records land in a database, a status
engine computes **green / orange / red** per equipment, alerts fire to
Teams/email + an in-app feed, and a **React portal** displays everything.

Phases implemented: **0–6** (scaffold, schema, sample generation, extraction,
status engine, notifications, portal). `seed.py` (Phase 7) is included.

## Architecture

```
Upload UI ──PDF──► FastAPI ──► Claude API (classify + extract → JSON)
                      │                │
                      ▼                ▼
                 SQLite (SQLAlchemy) ◄─ validated records + link to source PDF
                      │
                      ├─► Status engine (on-write + daily job): green/orange/red
                      │        └─► Teams webhook + email + in-app feed
                      ▼
                 React portal: cards, detail, upload, review queue, alerts
```

## Backend (`backend/`)

Python **3.11** (installed via Homebrew during setup; system 3.9 is too old).

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload      # http://127.0.0.1:8000
```

The venv (`backend/.venv`) already has all deps. To recreate:

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Configure secrets by copying the example (never commit `.env`):

```bash
cp .env.example .env            # add ANTHROPIC_API_KEY (required for extraction)
```

Teams / email are **optional** — unset env vars are skipped silently; the
in-app feed always works.

### Generate samples & seed

```bash
.venv/bin/python generate_samples.py         # 10 PDFs -> sample_docs/
.venv/bin/python -m app.seed                 # runs every PDF through the REAL
                                             # upload pipeline (needs API key)
```

Seeding produces a mixed fleet: **PMP-0041 green**, **CMP-0102 orange**,
**VLV-0210 red**, plus rentals/returns and one low-confidence record in the
review queue.

### Key endpoints

| Route | Purpose |
|---|---|
| `POST /documents/upload` | extract → persist → recompute status → notify |
| `GET /equipment`, `GET /equipment/{id}` | fleet + detail |
| `GET /review-queue`, `POST /documents/{id}/approve` | human review |
| `GET /notifications` | alert feed |
| `POST /admin/recompute` | force a status recompute (demo lever) |
| `GET /documents/{id}/file` | original source PDF (auditability) |

## Frontend (`frontend/`)

Vite + React + Tailwind. API base URL is a single constant in `src/config.js`
(override with `VITE_API_BASE`).

```bash
cd frontend
npm install
npm run dev                                   # http://localhost:5173
```

Pages: **Dashboard** (status cards + summary + filters, polls every 5s),
**Equipment detail** (specs, history timeline, linked source PDFs, status
explanation), **Upload** (drag-drop → live extraction → JSON review), **Review
queue**, **Notification feed**.

## Verified

- Phase 0/1: `/health`, all tables create + CRUD.
- Phase 2: 10 credible, format-varied PDFs with shared equipment codes.
- Phase 3 wiring / 4 / 5: ingestion → state transitions → status thresholds →
  review queue → notifications all pass (offline canned-extraction test); status
  engine unit-tested on the green/orange/red/overdue thresholds.
- Phase 6: builds clean; every endpoint the portal consumes returns the
  expected shape.

**Needs your `ANTHROPIC_API_KEY`** to run the live extraction (`seed.py` and the
full upload → card-flips-live loop).

## Hard rules honored

- `.env` / keys never committed (`.gitignore` excludes `.env`, `*.db`); ship
  `.env.example` only.
- Every stored record references its source document (auditability).
- Extraction degrades gracefully: validation failure → retry → review queue,
  never a crash or silent drop.
- All dates ISO `YYYY-MM-DD`, UTC assumed.
