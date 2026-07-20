# Equipment Document Intelligence POC

Vendor-side demo of an equipment lifecycle tracker. The system **reads PDFs
from the company's existing document store** (OneDrive) — there is no upload
screen. **Claude** classifies and extracts structured data, records land in a
database, a status engine computes **green / orange / red** per equipment,
alerts fire to Teams/email + an in-app feed, and a **read/review React portal**
displays everything.

Phases implemented: **0–6** (scaffold, schema, sample generation, extraction,
status engine, notifications, portal). `seed.py` (Phase 7) is included.

## Architecture

```
OneDrive folder ──poll──► FastAPI ingest ──► Claude API (classify + extract → JSON)
 (local inbox in dev)         │                       │
                             ▼                       ▼
                        SQLite (SQLAlchemy) ◄── validated records + link to source PDF
                             │
                             ├─► Status engine (on-write + daily job): green/orange/red
                             │        └─► Teams webhook + email + in-app feed
                             ▼
                        React portal (read/review): cards, detail, review queue, alerts
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

The extraction model defaults to **`claude-haiku-4-5`** (fast + cheap); override
with `ANTHROPIC_MODEL=claude-sonnet-5` in `.env` for tougher documents.

Teams / email are **optional** — unset env vars are skipped silently; the
in-app feed always works.

### Ingestion source (no upload UI)

Files are read from an existing store, configured by `INGEST_SOURCE`:

- **`local`** (default) — watches `LOCAL_INBOX_DIR` (or `./inbox`). Drop PDFs in
  and they're ingested. Ideal for the demo and for testing without Graph creds.
- **`onedrive`** — polls a OneDrive folder via Microsoft Graph (app-only auth;
  set `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`,
  `GRAPH_DRIVE_ID`, `GRAPH_FOLDER_PATH`, grant `Files.Read.All`).

Scanning is **idempotent** — each file's `source_id` (OneDrive item id+etag, or
local path+mtime) is recorded so re-scans skip already-ingested files. Set
`INGEST_POLL_MINUTES>0` to poll automatically, or trigger on demand:

```bash
curl -X POST http://127.0.0.1:8000/admin/ingest-now
```

### Tests

A `pytest` suite lives in `backend/tests/`. It runs against **isolated
temporary databases** and never touches `poc.db`.

```bash
.venv/bin/pip install -r requirements-dev.txt   # adds pytest
.venv/bin/pytest -v                             # mocked-extraction tests (no key needed)
```

- **Mocked tests** (default): status thresholds, the full ingest → status →
  review → notifications flow (canned extractions mirroring the sample PDFs),
  and the folder-scan dedupe. ~19 tests, no API calls.
- **Live tests** (`-m live`): exercise the **real** Claude extraction on the
  sample PDFs. They **auto-skip** until `ANTHROPIC_API_KEY` is set (env or
  `.env`). Once your key is in `.env`:

  ```bash
  .venv/bin/pytest -m live -v      # real classify + extract against Claude
  .venv/bin/pytest -v              # everything
  ```

### Generate samples & seed

```bash
.venv/bin/python generate_samples.py         # 10 PDFs -> sample_docs/
.venv/bin/python -m app.seed                 # runs every PDF through the REAL
                                             # pipeline (needs API key)
# — or — drop sample_docs/*.pdf into ./inbox and POST /admin/ingest-now
```

Either path produces a mixed fleet: **PMP-0041 green**, **CMP-0102 orange**,
**VLV-0210 red**, plus rentals/returns and one low-confidence record in the
review queue.

### Key endpoints

| Route | Purpose |
|---|---|
| `POST /admin/ingest-now` | scan the source folder and ingest new PDFs |
| `POST /documents/upload` | direct pipeline entry (e.g. a Graph webhook, or tests) |
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
explanation), **Review queue** (approve low-confidence extractions),
**Notification feed**. No upload page — ingestion is folder-driven.

## Verified

- Phase 0/1: `/health`, all tables create + CRUD.
- Phase 2: 10 credible, format-varied PDFs with shared equipment codes.
- Phase 3 wiring / 4 / 5: ingestion → state transitions → status thresholds →
  review queue → notifications all pass (offline canned-extraction test); status
  engine unit-tested on the green/orange/red/overdue thresholds.
- Ingestion source: local-folder scan ingests new PDFs and is idempotent
  (re-scans skip already-seen files by `source_id`).
- Phase 6: builds clean; every endpoint the portal consumes returns the
  expected shape.

**Needs your `ANTHROPIC_API_KEY`** to run the live extraction (`seed.py` /
folder ingestion → card-flips-live loop). The OneDrive path additionally needs
Microsoft Graph app credentials.

## Hard rules honored

- `.env` / keys never committed (`.gitignore` excludes `.env`, `*.db`); ship
  `.env.example` only.
- Every stored record references its source document (auditability).
- Extraction degrades gracefully: validation failure → retry → review queue,
  never a crash or silent drop.
- All dates ISO `YYYY-MM-DD`, UTC assumed.
