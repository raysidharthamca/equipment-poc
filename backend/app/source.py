"""Document ingestion sources — the system reads PDFs from an existing store
(the company's OneDrive) rather than offering an upload UI.

Two modes (INGEST_SOURCE):
  - "local":    scan a local folder (LOCAL_INBOX_DIR). Default; ideal for demo
                and testing without Graph credentials.
  - "onedrive": poll a OneDrive folder via Microsoft Graph (app-only auth).

Both feed the same ingest_pdf pipeline. Files already ingested (matched by a
stable source_id) are skipped, so repeated scans are idempotent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.ingest import ingest_pdf
from app.models import Document

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
DEFAULT_INBOX = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "inbox"))
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


@dataclass
class SourceFile:
    source_id: str          # stable identity for dedupe
    filename: str
    fetch: Callable[[], bytes]  # lazy download (only for new files)


def _already_ingested(db: Session, source_id: str) -> bool:
    return db.execute(
        select(Document.id).where(Document.source_id == source_id).limit(1)
    ).first() is not None


def scan_and_ingest(db: Session, ref_date: Optional[date] = None) -> dict:
    """List the source, ingest any new PDFs, skip already-seen ones.
    Commits per file. Returns a summary."""
    mode = settings.INGEST_SOURCE.lower()
    if mode == "onedrive":
        files = _list_onedrive()
    else:
        files = _list_local()

    ingested, skipped, errors = [], 0, []
    for sf in files:
        if _already_ingested(db, sf.source_id):
            skipped += 1
            continue
        try:
            pdf_bytes = sf.fetch()
            file_path = _cache_bytes(sf, pdf_bytes)
            result = ingest_pdf(
                db, filename=sf.filename, pdf_bytes=pdf_bytes,
                file_path=file_path, source_id=sf.source_id, ref_date=ref_date,
            )
            db.commit()
            ingested.append({
                "filename": sf.filename,
                "doc_type": result["document"]["doc_type"],
                "needs_review": result["document"]["needs_review"],
            })
        except Exception as e:  # one bad file must not stop the batch
            db.rollback()
            errors.append({"filename": sf.filename, "error": str(e)})

    return {
        "source": mode,
        "scanned": len(files),
        "ingested": ingested,
        "skipped": skipped,
        "errors": errors,
    }


def _cache_bytes(sf: SourceFile, pdf_bytes: bytes) -> str:
    """Persist bytes locally so the portal can show the original PDF.
    For local files we keep the original path instead of duplicating."""
    if sf.source_id.startswith("local:"):
        # source_id = local:<abspath>:<mtime>
        return sf.source_id.split(":", 2)[1]
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe = f"{sf.source_id.replace(':', '_').replace('/', '_')}_{os.path.basename(sf.filename)}"
    dest = os.path.join(UPLOAD_DIR, safe[:200])
    with open(dest, "wb") as f:
        f.write(pdf_bytes)
    return dest


# --- Local folder source ---------------------------------------------------- #

def _inbox_dir() -> str:
    return settings.LOCAL_INBOX_DIR or DEFAULT_INBOX


def _list_local() -> list[SourceFile]:
    inbox = _inbox_dir()
    if not os.path.isdir(inbox):
        return []
    out: list[SourceFile] = []
    for name in sorted(os.listdir(inbox)):
        if not name.lower().endswith(".pdf"):
            continue
        path = os.path.abspath(os.path.join(inbox, name))
        mtime = int(os.path.getmtime(path))
        sid = f"local:{path}:{mtime}"
        out.append(SourceFile(
            source_id=sid,
            filename=name,
            fetch=lambda p=path: open(p, "rb").read(),
        ))
    return out


# --- OneDrive (Microsoft Graph) source -------------------------------------- #

def _graph_token() -> str:
    for key in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET", "GRAPH_DRIVE_ID"):
        if not getattr(settings, key):
            raise RuntimeError(f"{key} is not set — required for INGEST_SOURCE=onedrive")
    url = f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token"
    with httpx.Client(timeout=15) as client:
        r = client.post(url, data={
            "client_id": settings.GRAPH_CLIENT_ID,
            "client_secret": settings.GRAPH_CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        })
        r.raise_for_status()
        return r.json()["access_token"]


def _list_onedrive() -> list[SourceFile]:
    token = _graph_token()
    drive = settings.GRAPH_DRIVE_ID
    folder = settings.GRAPH_FOLDER_PATH.strip("/")
    if folder:
        list_url = f"{GRAPH_BASE}/drives/{drive}/root:/{folder}:/children"
    else:
        list_url = f"{GRAPH_BASE}/drives/{drive}/root/children"
    headers = {"Authorization": f"Bearer {token}"}

    out: list[SourceFile] = []
    with httpx.Client(timeout=30, headers=headers) as client:
        url = list_url
        while url:
            r = client.get(url)
            r.raise_for_status()
            body = r.json()
            for item in body.get("value", []):
                name = item.get("name", "")
                if "file" not in item or not name.lower().endswith(".pdf"):
                    continue
                item_id = item["id"]
                etag = item.get("eTag", "")
                sid = f"onedrive:{item_id}:{etag}"
                out.append(SourceFile(
                    source_id=sid,
                    filename=name,
                    fetch=lambda iid=item_id, tok=token: _graph_download(iid, tok),
                ))
            url = body.get("@odata.nextLink")
    return out


def _graph_download(item_id: str, token: str) -> bytes:
    url = f"{GRAPH_BASE}/drives/{settings.GRAPH_DRIVE_ID}/items/{item_id}/content"
    with httpx.Client(timeout=60, follow_redirects=True,
                      headers={"Authorization": f"Bearer {token}"}) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.content
