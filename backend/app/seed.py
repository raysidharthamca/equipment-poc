"""Seed the database by running every sample PDF through the REAL upload
pipeline (not direct inserts) — the demo data must come from the actual
extraction path (Phase 7).

Usage:  python -m app.seed
"""
from __future__ import annotations

import os

from app.database import Base, SessionLocal, engine, init_db
from app.ingest import ingest_pdf
from app.main import recompute_and_notify

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_docs")

# Process in lifecycle order so state transitions compose correctly
# (spec -> sales -> rentals -> returns -> service records).
ORDER = [
    "spec_pmp_0041.pdf",
    "po_2026_0012_permian_sale.pdf",
    "po_2026_0018_gulfcoast.pdf",
    "po_2026_0021_anadarko.pdf",
    "rc_2026_0007_westtexas.pdf",
    "rc_2026_0009_bakken.pdf",
    "rr_2026_0003_return.pdf",
    "sr_2026_0051_pmp0041_green.pdf",
    "sr_2026_0052_cmp0102_orange.pdf",
    "sr_2026_0055_vlv0210_red.pdf",
]


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()


def main() -> None:
    print("Resetting database...")
    reset_db()
    db = SessionLocal()
    try:
        for filename in ORDER:
            path = os.path.abspath(os.path.join(SAMPLE_DIR, filename))
            if not os.path.exists(path):
                print(f"  SKIP (missing): {filename}")
                continue
            with open(path, "rb") as f:
                pdf_bytes = f.read()
            result = ingest_pdf(db, filename=filename, pdf_bytes=pdf_bytes, file_path=path)
            db.commit()
            doc = result["document"]
            flag = "  [REVIEW]" if doc["needs_review"] else ""
            print(f"  {filename:38s} -> {doc['doc_type']:16s} "
                  f"conf={doc['extraction_confidence']}{flag}")

        print("\nFinal recompute...")
        recompute_and_notify(db)

        # Summary
        from app.models import Equipment, Notification
        from sqlalchemy import select
        eqs = db.execute(select(Equipment).order_by(Equipment.equipment_code)).scalars().all()
        print("\nFleet:")
        for eq in eqs:
            print(f"  {eq.equipment_code:10s} {eq.status:6s} {eq.current_state:10s} {eq.name or ''}")
        counts = {"green": 0, "orange": 0, "red": 0}
        for eq in eqs:
            counts[eq.status] = counts.get(eq.status, 0) + 1
        n_notes = db.execute(select(Notification).where(Notification.channel == "in_app")).scalars().all()
        print(f"\nStatus counts: {counts}")
        print(f"In-app notifications: {len(n_notes)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
