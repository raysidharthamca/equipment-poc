"""Notification senders: Teams, email, and the in-app feed (Phase 5).

Channel behavior:
  - in-app feed: ALWAYS written (the portal renders these; the demo works with
    no webhook configured).
  - Teams: posted only if TEAMS_WEBHOOK_URL is set; skipped silently otherwise.
  - Email: sent only if SMTP_* or RESEND_API_KEY is configured; else skipped.

Dedupe: never re-fire for the same equipment + level within 24h.
"""
from __future__ import annotations

import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Equipment, Notification

DEDUPE_WINDOW = timedelta(hours=24)


def _deep_link(equipment_id: int) -> str:
    return f"{settings.PORTAL_BASE_URL.rstrip('/')}/equipment/{equipment_id}"


def _recently_notified(db: Session, equipment_id: int, level: str) -> bool:
    cutoff = datetime.now(timezone.utc) - DEDUPE_WINDOW
    stmt = (
        select(Notification)
        .where(
            Notification.equipment_id == equipment_id,
            Notification.level == level,
            Notification.sent_at >= cutoff,
        )
        .limit(1)
    )
    return db.execute(stmt).scalars().first() is not None


def notify(
    db: Session,
    equipment: Equipment,
    message: str,
    level: str,
    *,
    dedupe: bool = True,
) -> Optional[Notification]:
    """Fire a notification across all configured channels.

    Returns the in-app Notification row, or None if deduped. Caller commits.
    """
    if dedupe and _recently_notified(db, equipment.id, level):
        return None

    # 1. In-app feed row (always).
    row = Notification(
        equipment_id=equipment.id,
        channel="in_app",
        message=message,
        level=level,
    )
    db.add(row)

    # 2. Teams (optional).
    if settings.TEAMS_WEBHOOK_URL:
        try:
            _post_teams(equipment, message, level)
            db.add(Notification(equipment_id=equipment.id, channel="teams",
                                message=message, level=level))
        except Exception as e:  # never let a webhook failure break ingestion
            print(f"[notify] Teams post failed: {e}")

    # 3. Email (optional).
    if _email_configured():
        try:
            _send_email(equipment, message, level)
            db.add(Notification(equipment_id=equipment.id, channel="email",
                                message=message, level=level))
        except Exception as e:
            print(f"[notify] Email send failed: {e}")

    return row


# --- Trigger helpers -------------------------------------------------------- #

def notify_status_change(db: Session, equipment: Equipment, new_status: str,
                         days_until_due: Optional[int]) -> Optional[Notification]:
    if new_status == "orange":
        level = "warning"
        due = f"{days_until_due} days" if days_until_due is not None else "soon"
        msg = f"{equipment.equipment_code} ({equipment.name or 'equipment'}) service due in {due}."
    elif new_status == "red":
        level = "critical"
        if days_until_due is not None and days_until_due < 0:
            msg = (f"{equipment.equipment_code} ({equipment.name or 'equipment'}) "
                   f"service OVERDUE by {abs(days_until_due)} days.")
        else:
            msg = f"{equipment.equipment_code} ({equipment.name or 'equipment'}) is in service / requires attention."
    else:
        return None
    return notify(db, equipment, msg, level)


def notify_due_back(db: Session, equipment: Equipment, days_left: int) -> Optional[Notification]:
    msg = (f"Rental return due for {equipment.equipment_code} "
           f"({equipment.name or 'equipment'}) in {days_left} days.")
    return notify(db, equipment, msg, "warning")


# --- Channel implementations ------------------------------------------------ #

def _post_teams(equipment: Equipment, message: str, level: str) -> None:
    color = {"warning": "Warning", "critical": "Attention"}.get(level, "Default")
    card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [
                        {"type": "TextBlock", "size": "Large", "weight": "Bolder",
                         "color": color, "text": f"Equipment Alert: {equipment.equipment_code}"},
                        {"type": "TextBlock", "wrap": True, "text": message},
                        {"type": "FactSet", "facts": [
                            {"title": "Name", "value": equipment.name or "-"},
                            {"title": "Status", "value": equipment.status},
                            {"title": "State", "value": equipment.current_state},
                        ]},
                    ],
                    "actions": [
                        {"type": "Action.OpenUrl", "title": "Open in portal",
                         "url": _deep_link(equipment.id)},
                    ],
                },
            }
        ],
    }
    with httpx.Client(timeout=10) as client:
        r = client.post(settings.TEAMS_WEBHOOK_URL, json=card)
        r.raise_for_status()


def _email_configured() -> bool:
    smtp_ok = all([settings.SMTP_HOST, settings.SMTP_FROM, settings.SMTP_TO])
    return bool(settings.RESEND_API_KEY) or smtp_ok


def _email_html(equipment: Equipment, message: str, level: str) -> str:
    color = {"warning": "#d97706", "critical": "#b91c1c"}.get(level, "#374151")
    return f"""\
<div style="font-family:system-ui,sans-serif">
  <h2 style="color:{color};margin:0 0 8px">Equipment Alert: {equipment.equipment_code}</h2>
  <p style="font-size:15px">{message}</p>
  <table style="border-collapse:collapse;font-size:13px">
    <tr><td style="padding:2px 12px 2px 0;color:#666">Name</td><td>{equipment.name or '-'}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#666">Status</td><td>{equipment.status}</td></tr>
    <tr><td style="padding:2px 12px 2px 0;color:#666">State</td><td>{equipment.current_state}</td></tr>
  </table>
  <p><a href="{_deep_link(equipment.id)}">Open in portal</a></p>
</div>"""


def _send_email(equipment: Equipment, message: str, level: str) -> None:
    subject = f"[{level.upper()}] {equipment.equipment_code} — {message[:60]}"
    html = _email_html(equipment, message, level)

    if settings.RESEND_API_KEY:
        with httpx.Client(timeout=10) as client:
            r = client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={
                    "from": settings.SMTP_FROM or "alerts@equipment-poc.local",
                    "to": [settings.SMTP_TO] if settings.SMTP_TO else [],
                    "subject": subject,
                    "html": html,
                },
            )
            r.raise_for_status()
        return

    # SMTP fallback.
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = settings.SMTP_TO
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
