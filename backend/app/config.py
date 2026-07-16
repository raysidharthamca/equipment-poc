"""Centralized configuration loaded from environment / .env file."""
from __future__ import annotations

import os

from dotenv import load_dotenv

# Load .env once at import time. Safe no-op if the file is absent.
load_dotenv()


class Settings:
    """Plain settings holder. Kept simple for the POC — no pydantic-settings."""

    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
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


settings = Settings()
