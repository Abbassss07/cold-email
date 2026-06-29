"""Resend email sender. Swap this module to change provider."""
from __future__ import annotations

import logging
import os
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
               attachments: Optional[list] = None) -> str:
    """Send an email through Resend. Returns the provider message ID.
    attachments: list of {"filename": str, "content": base64-str} dicts.
    """
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

    result = resend.Emails.send(params)
    # Resend returns dict-like with 'id'
    if isinstance(result, dict):
        msg_id = result.get("id") or result.get("message_id") or ""
    else:
        msg_id = getattr(result, "id", "") or getattr(result, "message_id", "")
    if not msg_id:
        raise RuntimeError(f"Resend did not return a message id: {result}")
    return msg_id


def check_status() -> dict:
    """Lightweight check whether keys appear configured."""
    return {
        "configured": bool(os.environ.get("RESEND_API_KEY", "").strip()),
        "from_email": os.environ.get("FROM_EMAIL", ""),
        "from_name": os.environ.get("FROM_NAME", ""),
    }
