"""Resend email sender with retries. Swap this module to change provider."""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import resend

logger = logging.getLogger(__name__)


def _ensure_key() -> str:
    key = os.environ.get("RESEND_API_KEY", "").strip()
    if not key:
        raise RuntimeError("RESEND_API_KEY is not set")
    resend.api_key = key
    return key


def send_email(to_email: str, subject: str, html: str, text: Optional[str] = None,
               attachments: Optional[list] = None, max_retries: int = 2) -> str:
    """Send email through Resend with up to 2 additional retries. Returns message id."""
    _ensure_key()
    from_email = os.environ.get("FROM_EMAIL", "").strip()
    from_name = os.environ.get("FROM_NAME", "").strip() or "SDU Global Auditing"
    if not from_email:
        raise RuntimeError("FROM_EMAIL is not set")

    params: dict = {
        "from": f"{from_name} <{from_email}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    }
    if text:
        params["text"] = text
    if attachments:
        params["attachments"] = attachments

    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            result = resend.Emails.send(params)
            msg_id = (result.get("id") if isinstance(result, dict) else getattr(result, "id", "")) or ""
            if not msg_id:
                raise RuntimeError(f"Resend returned no id: {result}")
            return msg_id
        except Exception as e:
            last_err = e
            logger.warning("Resend attempt %d failed: %s", attempt + 1, e)
            # Do not retry obvious 4xx-style configuration errors
            msg = str(e).lower()
            if "verify a domain" in msg or "invalid_from" in msg or "401" in msg or "forbidden" in msg:
                break
            if attempt < max_retries:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(str(last_err))


def check_status() -> dict:
    return {
        "configured": bool(os.environ.get("RESEND_API_KEY", "").strip()),
        "from_email": os.environ.get("FROM_EMAIL", ""),
        "from_name": os.environ.get("FROM_NAME", ""),
    }
