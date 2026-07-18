"""Newsletter, Contact Lists, Campaign History. All non-AI. Additive router."""
from __future__ import annotations

import base64
import csv as csv_lib
import io
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, EmailStr, Field

from auth import require_session
from email_sender import send_email
from rate_limiter import daily_count, daily_increment

logger = logging.getLogger(__name__)

nl = APIRouter(prefix="/api", tags=["newsletter"])

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024  # 8 MB per file (Resend cap ~10 MB total)
ALLOWED_EXT = {".pdf", ".docx", ".xlsx", ".doc", ".xls", ".txt", ".csv", ".png", ".jpg", ".jpeg"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- DB binding ----------
_db = {"contacts": None, "campaigns": None, "logs": None, "emails": None}


def bind_db(contact_lists_col, campaigns_col, logs_col, emails_col):
    _db["contacts"] = contact_lists_col
    _db["campaigns"] = campaigns_col
    _db["logs"] = logs_col
    _db["emails"] = emails_col


# ---------- Models ----------
class ContactListRenameIn(BaseModel):
    name: str


class NewsletterSendIn(BaseModel):
    list_id: str
    subject: str
    body_html: str = ""
    body_text: str = ""
    from_email: Optional[str] = None
    from_name: Optional[str] = None
    campaign_name: str = "Newsletter"
    test_only: bool = False
    test_to: Optional[EmailStr] = None
    attachments: list[dict] = Field(default_factory=list)  # [{filename, content_b64}]


# ---------- Contact Lists ----------
def _parse_contacts(raw: bytes) -> tuple[list[dict], list[dict]]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1", errors="replace")
    reader = csv_lib.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], [{"reason": "CSV has no headers"}]
    valid, skipped = [], []
    for i, row in enumerate(reader, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        email = r.get("contact_email") or r.get("email") or ""
        if not email or not EMAIL_RE.match(email):
            skipped.append({"row": i, "reason": "invalid email", "data": r})
            continue
        valid.append({
            "contact_email": email,
            "contact_name": r.get("contact_name") or r.get("name") or "",
            "company_name": r.get("company_name") or r.get("company") or "",
            "industry": r.get("industry", ""),
            "notes": r.get("notes", ""),
        })
    return valid, skipped


@nl.get("/contact-lists")
async def list_contact_lists(_u: str = Depends(require_session)):
    items = await _db["contacts"].find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for it in items:
        it["count"] = len(it.get("contacts", []))
        it.pop("contacts", None)  # don't ship the whole list on the index view
    return items


@nl.get("/contact-lists/{list_id}")
async def get_contact_list(list_id: str, _u: str = Depends(require_session)):
    item = await _db["contacts"].find_one({"id": list_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "List not found")
    return item


@nl.post("/contact-lists")
async def upload_contact_list(file: UploadFile = File(...), name: str = Form(...),
                              _u: str = Depends(require_session)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(413, "CSV exceeds 2 MB")
    valid, skipped = _parse_contacts(raw)
    if not valid:
        raise HTTPException(400, f"No valid contacts. First reason: {skipped[0]['reason'] if skipped else 'empty'}")
    doc = {
        "id": str(uuid.uuid4()),
        "name": name.strip(),
        "contacts": valid,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await _db["contacts"].insert_one(doc)
    return {"id": doc["id"], "count": len(valid), "skipped": len(skipped)}


@nl.put("/contact-lists/{list_id}/rename")
async def rename_contact_list(list_id: str, payload: ContactListRenameIn,
                              _u: str = Depends(require_session)):
    r = await _db["contacts"].update_one({"id": list_id},
                                          {"$set": {"name": payload.name.strip(), "updated_at": _now()}})
    if r.matched_count == 0:
        raise HTTPException(404, "List not found")
    return {"ok": True}


@nl.put("/contact-lists/{list_id}/replace")
async def replace_contact_list(list_id: str, file: UploadFile = File(...),
                                _u: str = Depends(require_session)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")
    raw = await file.read()
    valid, skipped = _parse_contacts(raw)
    if not valid:
        raise HTTPException(400, "No valid contacts")
    r = await _db["contacts"].update_one({"id": list_id},
                                          {"$set": {"contacts": valid, "updated_at": _now()}})
    if r.matched_count == 0:
        raise HTTPException(404, "List not found")
    return {"count": len(valid), "skipped": len(skipped)}


@nl.delete("/contact-lists/{list_id}")
async def delete_contact_list(list_id: str, _u: str = Depends(require_session)):
    r = await _db["contacts"].delete_one({"id": list_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "List not found")
    return {"ok": True}


# ---------- Newsletter send ----------
def _validate_attachments(atts: list[dict]) -> list[dict]:
    """Attachments arrive as [{filename, content_b64}]. Validate size + extension."""
    out = []
    total = 0
    for a in atts or []:
        fn = (a.get("filename") or "").strip()
        b64 = a.get("content_b64") or ""
        if not fn or not b64:
            continue
        ext = os.path.splitext(fn)[1].lower()
        if ext not in ALLOWED_EXT:
            raise HTTPException(400, f"Attachment '{fn}': type not allowed")
        try:
            raw = base64.b64decode(b64)
        except Exception:
            raise HTTPException(400, f"Attachment '{fn}': invalid base64")
        if len(raw) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(413, f"Attachment '{fn}' exceeds 8 MB")
        total += len(raw)
        if total > 10 * 1024 * 1024:
            raise HTTPException(413, "Attachments total exceeds 10 MB")
        out.append({"filename": fn, "content": b64})
    return out


def _personalize(text: str, contact: dict) -> str:
    return (text or "").replace("{{name}}", contact.get("contact_name") or "there") \
        .replace("{{company}}", contact.get("company_name") or "")


@nl.post("/newsletter/send")
async def newsletter_send(payload: NewsletterSendIn, _u: str = Depends(require_session)):
    lst = await _db["contacts"].find_one({"id": payload.list_id}, {"_id": 0})
    if not lst:
        raise HTTPException(404, "Contact list not found")
    contacts = lst.get("contacts", [])
    if not contacts:
        raise HTTPException(400, "Contact list is empty")

    if payload.test_only:
        test_to = payload.test_to or os.environ.get("NEWSLETTER_FROM_EMAIL",
                                                    os.environ.get("FROM_EMAIL", ""))
        if not test_to:
            raise HTTPException(400, "No test recipient configured")
        contacts = [{"contact_email": test_to, "contact_name": "Test",
                     "company_name": lst.get("name", "")}]

    from_email = (payload.from_email or os.environ.get("NEWSLETTER_FROM_EMAIL")
                  or os.environ.get("FROM_EMAIL", "")).strip()
    from_name = (payload.from_name or os.environ.get("NEWSLETTER_FROM_NAME")
                 or os.environ.get("FROM_NAME", "SDU Connect")).strip()
    if not from_email:
        raise HTTPException(400, "From email not configured")

    attachments = _validate_attachments(payload.attachments)

    # temporarily override env for send_email
    prev_from_email = os.environ.get("FROM_EMAIL", "")
    prev_from_name = os.environ.get("FROM_NAME", "")
    os.environ["FROM_EMAIL"] = from_email
    os.environ["FROM_NAME"] = from_name

    campaign_id = str(uuid.uuid4())
    started = _now()
    results = {"sent": 0, "failed": 0, "errors": []}

    try:
        for c in contacts:
            html = _personalize(payload.body_html, c) or _personalize(payload.body_text, c)
            plain = _personalize(payload.body_text, c) or None
            subject = _personalize(payload.subject, c)
            try:
                msg_id = send_email(c["contact_email"], subject, html, plain,
                                     attachments=attachments)
                results["sent"] += 1
                await _db["logs"].insert_one({
                    "id": str(uuid.uuid4()),
                    "campaign_id": campaign_id,
                    "kind": "newsletter",
                    "company_name": c.get("company_name", ""),
                    "contact_email": c["contact_email"],
                    "subject": subject,
                    "status": "sent",
                    "provider": "resend",
                    "message_id": msg_id,
                    "timestamp": _now(),
                    "error": "",
                })
                daily_increment("sent")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"email": c["contact_email"], "error": str(e)})
                await _db["logs"].insert_one({
                    "id": str(uuid.uuid4()),
                    "campaign_id": campaign_id,
                    "kind": "newsletter",
                    "company_name": c.get("company_name", ""),
                    "contact_email": c["contact_email"],
                    "subject": subject,
                    "status": "failed",
                    "provider": "resend",
                    "timestamp": _now(),
                    "error": str(e),
                })
    finally:
        os.environ["FROM_EMAIL"] = prev_from_email
        os.environ["FROM_NAME"] = prev_from_name

    if not payload.test_only:
        await _db["campaigns"].insert_one({
            "id": campaign_id,
            "name": payload.campaign_name,
            "kind": "newsletter",
            "list_id": payload.list_id,
            "list_name": lst.get("name", ""),
            "from_email": from_email,
            "from_name": from_name,
            "subject": payload.subject,
            "total": len(contacts),
            "sent": results["sent"],
            "failed": results["failed"],
            "started_at": started,
            "finished_at": _now(),
            "attachments_count": len(attachments),
        })

    return {"campaign_id": campaign_id, **results}


# ---------- Campaign History ----------
@nl.get("/campaigns")
async def list_campaigns(_u: str = Depends(require_session)):
    items = await _db["campaigns"].find({}, {"_id": 0}).sort("started_at", -1).to_list(500)
    return items


@nl.get("/campaigns/{campaign_id}")
async def get_campaign(campaign_id: str, _u: str = Depends(require_session)):
    item = await _db["campaigns"].find_one({"id": campaign_id}, {"_id": 0})
    if not item:
        raise HTTPException(404, "Campaign not found")
    # attach engagement summary from logs
    events = await _db["logs"].find({"campaign_id": campaign_id}, {"_id": 0}).to_list(5000)
    item["events"] = events
    return item


# ---------- Newsletter analytics ----------
@nl.get("/newsletter/stats")
async def newsletter_stats(_u: str = Depends(require_session)):
    pipe = [
        {"$match": {"kind": "newsletter"}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]
    counts = {"sent": 0, "failed": 0, "delivered": 0, "opened": 0, "clicked": 0}
    async for row in _db["logs"].aggregate(pipe):
        s = row["_id"]
        if s in counts:
            counts[s] = row["n"]
    total = counts["sent"] + counts["failed"]
    counts["total"] = total
    return counts
