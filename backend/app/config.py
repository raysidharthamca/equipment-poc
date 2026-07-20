"""Centralized configuration loaded from environment / .env file."""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Load .env once at import time. Safe no-op if the file is absent.
load_dotenv()


class Settings:
    """Plain settings holder. Kept simple for the POC — no pydantic-settings."""

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # Extraction model. Haiku 4.5 is fast + cheap and ample for this mechanical
    # classify/extract task; override to claude-sonnet-5 for tougher documents.
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./poc.db")

    # Optional alert channels (Phase 5).
    TEAMS_WEBHOOK_URL: str = os.getenv("TEAMS_WEBHOOK_URL", "")
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")
    SMTP_TO: str = os.getenv("SMTP_TO", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

    PORTAL_BASE_URL: str = os.getenv("PORTAL_BASE_URL", "http://localhost:5173")

    # --- Document ingestion source ---
    # The system reads PDFs from an existing store (no upload UI).
    #   "local"    -> watch LOCAL_INBOX_DIR (default; great for local demo/testing)
    #   "onedrive" -> poll a OneDrive folder via Microsoft Graph
    INGEST_SOURCE: str = os.getenv("INGEST_SOURCE", "local")
    LOCAL_INBOX_DIR: str = os.getenv("LOCAL_INBOX_DIR", "")  # abs path; blank -> ./inbox
    # 0 disables the automatic poll (use POST /admin/ingest-now on demand).
    INGEST_POLL_MINUTES: int = int(os.getenv("INGEST_POLL_MINUTES", "0"))

    # Microsoft Graph (client-credentials / app-only) for INGEST_SOURCE=onedrive.
    GRAPH_TENANT_ID: str = os.getenv("GRAPH_TENANT_ID", "")
    GRAPH_CLIENT_ID: str = os.getenv("GRAPH_CLIENT_ID", "")
    GRAPH_CLIENT_SECRET: str = os.getenv("GRAPH_CLIENT_SECRET", "")
    GRAPH_DRIVE_ID: str = os.getenv("GRAPH_DRIVE_ID", "")  # target drive id
    GRAPH_FOLDER_PATH: str = os.getenv("GRAPH_FOLDER_PATH", "")  # e.g. "Equipment/Incoming"


settings = Settings()
