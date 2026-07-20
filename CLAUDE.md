# CLAUDE.md — Equipment Document Intelligence POC

Project context and conventions for Claude Code. Read this before making changes.

## What this is

Vendor-side POC that tracks oil & gas equipment lifecycle. PDFs (purchase
orders, rental contracts, service records, returns, spec sheets) are read from
an **existing document store**, **Claude** classifies + extracts structured
data, records land in SQLite, a status engine computes **green/orange/red** per
equipment, alerts fire (Teams/email/in-app), and a **read/review React portal**
displays everything. Build workflow: `equipment-poc-workflow.md` (phases 0–6
are done).

## KEY DECISIONS (do not regress these)

- **No upload UI.** Files are read from the company's existing store (OneDrive).
  The portal is **read/review only** (dashboard, equipment detail, review queue,
  alerts). There is no drag-drop upload page — it was intentionally removed.
- **Ingestion source is configurable** via `INGEST_SOURCE` env:
  - `local` (default) — watches `LOCAL_INBOX_DIR` (or `backend/inbox/`).
  - `onedrive` — polls a OneDrive folder via Microsoft Graph (app-only auth,
    `GRAPH_*` env vars). Code is written but needs real Graph creds to run live.
  - Both feed the **same** `ingest_pdf` pipeline; only the trigger differs.
- **Extraction model = Haiku** (`claude-haiku-4-5`) by default, override with
  `ANTHROPIC_MODEL` (e.g. `claude-sonnet-5`). Set in `app/config.py`.
- **Auditability:** every `transactions` / `service_records` row links back to
  its source `documents` row. Keep this invariant.
- **Graceful degradation:** extraction validation failure → retry once → review
  queue. Confidence < 0.8 → `needs_review`. Never crash / silently drop.

## FOLDERS — what reads/writes what (common confusion)

| Folder | Role | Direction |
|---|---|---|
| `backend/sample_docs/` | 10 generated demo PDFs (fixed inputs) | `app.seed` **reads** |
| `backend/inbox/` | Local watch folder — the OneDrive stand-in | `/admin/ingest-now` / poller **reads** |
| `backend/uploads/` | Cache of ingested originals (so the portal can serve the source PDF) | app **writes** (never an input) |

- `app.seed` reads `sample_docs/` and points `file_path` at those paths — it does
  **not** copy into `uploads/`, so `uploads/` stays empty after a seed. Expected.
- `uploads/` only fills for the OneDrive path or the direct upload endpoint.

## RUN

```bash
# Backend (from backend/, foreground — no & or echo "$!" ; zsh chokes on the !)
cd backend && .venv/bin/uvicorn app.main:app --port 8000

# Frontend (separate terminal)
cd frontend && npm run dev            # http://localhost:5173
```

Python 3.11 venv at `backend/.venv` (deps installed). Frontend deps in
`frontend/node_modules`.

## GET DATA IN

Two ways, reading from **different** folders:

```bash
# 1. Demo shortcut — reads sample_docs/, real Claude pipeline
cd backend && .venv/bin/python -m app.seed

# 2. Folder-drop (OneDrive analog) — put PDFs in backend/inbox/, then:
curl -X POST http://127.0.0.1:8000/admin/ingest-now
```

## RESET / CLEAN THE DB

**Gotcha:** `Base.metadata.drop_all()` is a silent no-op unless `app.models` is
imported first (that's what registers the tables). Use the helper — do NOT
hand-roll `drop_all` in a one-liner without importing models.

```bash
cd backend
# clean (empty tables, keep schema)
.venv/bin/python -c "from app.database import reset_db; reset_db(); print('cleaned')"
# or foolproof full wipe
rm -f poc.db
# verify
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('poc.db'); print({t: c.execute('select count(*) from '+t).fetchone()[0] for t in ('equipment','documents','transactions','service_records','notifications')})"
```

**SQLite is single-writer:** stop the uvicorn server (and refresh DBeaver) before
resetting/seeding from another terminal, or the running app can hold locks.
`poc.db` persists between runs — it only changes when you seed/ingest; that's the
app's real database, not test state.

## TESTS

```bash
cd backend
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -m "not live"    # 19 mocked unit tests (fake_run, temp DBs — never touch poc.db)
.venv/bin/pytest -m live          # 4 live tests, real Claude (needs ANTHROPIC_API_KEY)
.venv/bin/pytest                  # all 23
```

- Tests use **isolated temp databases** (`tests/conftest.py`) and never touch
  `poc.db`.
- `fake_run` canned extractions live in `tests/canned.py` (mirror the sample
  PDFs). Live tests hit the real API and auto-skip without a key.

## SECRETS

- `backend/.env` holds `ANTHROPIC_API_KEY` (+ `GRAPH_*`). **Gitignored** — never
  commit it. Ship `.env.example` only.
- If a key is ever pasted into a chat/log, treat it as compromised and rotate it.

## LAYOUT

```
backend/
  app/        source package (config, database, models, schemas, extraction,
              ingest, status, notify, source, main, seed)
  tests/      pytest suite (conftest, canned, test_*.py)
  sample_docs/  generated demo PDFs      inbox/  local ingestion folder
  generate_samples.py  requirements*.txt  pytest.ini  .env(.example)
frontend/     Vite + React + Tailwind (read/review portal; no upload page)
```
