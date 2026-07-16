"""Green / orange / red status engine (Phase 4).

Rules (from the workflow):

    days_until_due = (last_service_date + service_interval_days) - today
      (use next_due_date from the latest service record when present)

    GREEN  : days_until_due > 30 and current_state == available
    ORANGE : 0 <= days_until_due <= 30
    RED    : days_until_due < 0 (overdue) or current_state == in_service

Precedence used here (so the three rules compose deterministically):
    1. RED    if in_service, or overdue (days_until_due < 0)
    2. ORANGE if 0 <= days_until_due <= 30
    3. GREEN  otherwise (healthy / not-yet-due / no service obligation)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Equipment, ServiceRecord

GREEN = "green"
ORANGE = "orange"
RED = "red"


def today() -> date:
    """Reference date. Isolated so tests/demo can pin it."""
    return date.today()


def _latest_service(db: Session, equipment_id: int) -> Optional[ServiceRecord]:
    stmt = (
        select(ServiceRecord)
        .where(ServiceRecord.equipment_id == equipment_id)
        .order_by(ServiceRecord.service_date.desc().nullslast(), ServiceRecord.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def compute_due_date(eq: Equipment, db: Session) -> Optional[date]:
    """Next service due date: prefer the latest record's next_due_date, else
    last_service_date + interval. None when there is no service info."""
    svc = _latest_service(db, eq.id)
    if svc is not None and svc.next_due_date is not None:
        return svc.next_due_date
    base = eq.last_service_date or (svc.service_date if svc else None)
    if base is not None:
        return base + timedelta(days=eq.service_interval_days or 180)
    return None


def days_until_due(eq: Equipment, db: Session, ref: Optional[date] = None) -> Optional[int]:
    ref = ref or today()
    due = compute_due_date(eq, db)
    if due is None:
        return None
    return (due - ref).days


def compute_status(eq: Equipment, db: Session, ref: Optional[date] = None) -> str:
    d = days_until_due(eq, db, ref)
    if eq.current_state == "in_service":
        return RED
    if d is not None and d < 0:
        return RED
    if d is not None and 0 <= d <= 30:
        return ORANGE
    return GREEN


@dataclass
class StatusChange:
    equipment_id: int
    equipment_code: str
    old_status: str
    new_status: str
    days_until_due: Optional[int]

    @property
    def worsened(self) -> bool:
        rank = {GREEN: 0, ORANGE: 1, RED: 2}
        return rank[self.new_status] > rank[self.old_status]


def recompute_one(eq: Equipment, db: Session, ref: Optional[date] = None) -> StatusChange:
    old = eq.status
    new = compute_status(eq, db, ref)
    eq.status = new
    return StatusChange(
        equipment_id=eq.id,
        equipment_code=eq.equipment_code,
        old_status=old,
        new_status=new,
        days_until_due=days_until_due(eq, db, ref),
    )


def recompute_all(db: Session, ref: Optional[date] = None) -> list[StatusChange]:
    """Recompute every equipment's status; returns the set of changes.
    Caller commits."""
    changes: list[StatusChange] = []
    for eq in db.execute(select(Equipment)).scalars():
        change = recompute_one(eq, db, ref)
        if change.old_status != change.new_status:
            changes.append(change)
    return changes
