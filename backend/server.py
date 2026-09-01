"""SDU Global Cold Email Outreach – FastAPI backend."""
from __future__ import annotations

import logging
import os
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import resend
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth import (  # noqa: E402
    clear_session_cookie,
    create_session_cookie,
    require_session,
    set_password,
    verify_password,
)
from csv_handler import parse_csv  # noqa: E402
from email_generator import (  # noqa: E402
    GeneratedEmail,
    fetch_website_summary,
    generate_email,
    read_company_context,
    render_html,
    render_plain,
)
from email_sender import check_status as resend_status, send_email  # noqa: E402
from greeting import build_greeting  # noqa: E402
from rate_limiter import (  # noqa: E402
    allow,
    daily_count,
    release_daily_send,
    reserve_daily_send,
)
from crm import add_timeline, bind_db, crm as crm_router  # noqa: E402
from newsletter import bind_db as bind_nl_db, nl as newsletter_router  # noqa: E402
from database import (  # noqa: E402
    Collection,
    get_setting,
    get_settings_map,
    set_setting,
    storage_download,
    storage_info,
    storage_remove,
    storage_upload,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sdu")

# ---------- Supabase Postgres ----------
emails_col = Collection("leads")
logs_col = Collection("send_logs")
website_cache_col = Collection("website_cache")
tasks_col = Collection("tasks")
meetings_col = Collection("meetings")
timeline_col = Collection("timeline")
contact_lists_col = Collection("contact_lists")
campaigns_col = Collection("campaigns")
bind_db(emails_col, tasks_col, meetings_col, timeline_col, logs_col)
bind_nl_db(contact_lists_col, campaigns_col, logs_col, emails_col)

# ---------- PDF attachment ----------
PDF_STORAGE_PATH = "company/company-profile.pdf"


async def _build_pdf_attachment() -> list:
    """Return a Resend-compatible attachment from private Supabase Storage."""
    import base64
    try:
        data = await storage_download(PDF_STORAGE_PATH)
    except Exception:
        return []
    content = base64.b64encode(data).decode("ascii")
    return [{"filename": "SDU-Global-Company-Profile.pdf", "content": content}]

# ---------- App ----------
app = FastAPI(title="SDU Cold Email Outreach")
api = APIRouter(prefix="/api")


# ---------- Models ----------
class EmailDoc(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_name: str
    contact_email: EmailStr
    contact_name: str = ""
    website: str = ""
    industry: str = ""
    notes: str = ""
    country: str = ""
    phone: str = ""
    stage: str = "new_lead"
    services: list[str] = Field(default_factory=list)
    internal_notes: str = ""
    last_contact_at: Optional[str] = None
    subject: str = ""
    intro: str = ""
    status: str = "pending"  # pending|generated|sending|sent|failed
    provider: str = "resend"
    message_id: str = ""
    error: str = ""
    gen_ms: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sent_at: Optional[str] = None


class LoginIn(BaseModel):
    password: str


class GenerateIn(BaseModel):
    ids: List[str]


class SendIn(BaseModel):
    ids: List[str]


class UpdateEmailIn(BaseModel):
    subject: Optional[str] = None
    intro: Optional[str] = None


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: str


class ContextIn(BaseModel):
    content: str


class LimitIn(BaseModel):
    daily_limit: int


# Whitelist of env keys editable via Settings UI
EDITABLE_ENV_KEYS = {
    "COMPANY_NAME", "FROM_NAME", "FROM_EMAIL", "DESIGNATION",
    "PHONE", "COMPANY_WEBSITE", "GEMINI_API_KEY", "RESEND_API_KEY",
    "NEWSLETTER_FROM_EMAIL", "NEWSLETTER_FROM_NAME",
    "AI_RESEARCH_ENABLED", "SEND_DELAY_SECONDS",
}


class EnvIn(BaseModel):
    updates: dict[str, str]


# ---------- Auth ----------
@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    if not allow("login", 10, 60):
        raise HTTPException(429, "Too many login attempts. Try again shortly.")
    if not await verify_password(payload.password):
        raise HTTPException(401, "Invalid password")
    create_session_cookie(response, "admin")
    return {"ok": True}


@api.post("/auth/logout")
async def logout(response: Response, _user: str = Depends(require_session)):
    clear_session_cookie(response)
    return {"ok": True}


@api.get("/auth/me")
async def me(user: str = Depends(require_session)):
    return {"user": user}


# ---------- CSV upload ----------
@api.post("/upload")
async def upload_csv(file: UploadFile = File(...), _user: str = Depends(require_session)):
    raw = await file.read()
    max_size = 2 * 1024 * 1024  # 2 MB
    if len(raw) > max_size:
        raise HTTPException(413, f"CSV exceeds {max_size} bytes")
    max_rows = int(os.environ.get("MAX_CSV_ROWS", "500"))
    valid, skipped = parse_csv(raw, max_rows=max_rows)

    docs: list[EmailDoc] = []
    for row in valid:
        docs.append(EmailDoc(
            company_name=row["company_name"],
            contact_email=row["contact_email"],
            contact_name=row.get("contact_name", ""),
            website=row.get("website", ""),
            industry=row.get("industry", ""),
            notes=row.get("notes", ""),
        ))
    if docs:
        await emails_col.insert_many([d.model_dump() for d in docs])
    return {
        "imported": len(docs),
        "skipped": skipped,
        "ids": [d.id for d in docs],
    }


# ---------- List + stats ----------
@api.get("/emails")
async def list_emails(status: Optional[str] = None, _user: str = Depends(require_session)):
    query: dict = {}
    if status:
        query["status"] = status
    items = await emails_col.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return items


@api.get("/stats")
async def stats(_user: str = Depends(require_session)):
    pipe = [{"$group": {"_id": "$status", "n": {"$sum": 1}}}]
    counts = {"pending": 0, "generated": 0, "sent": 0, "failed": 0, "sending": 0}
    async for row in emails_col.aggregate(pipe):
        counts[row["_id"]] = row["n"]
    total = sum(counts.values())
    counts["total"] = total
    counts["draft"] = counts["generated"]  # alias
    counts["daily_sent"] = await daily_count()
    counts["daily_limit"] = int(await get_setting(
        "daily_email_limit", os.environ.get("DAILY_EMAIL_LIMIT", "200")
    ))

    # Today's emails (created today UTC)
    today_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    counts["today"] = await emails_col.count_documents({"created_at": {"$regex": f"^{today_prefix}"}})

    # Success rate
    sent_or_failed = counts["sent"] + counts["failed"]
    counts["success_rate"] = round(counts["sent"] * 100.0 / sent_or_failed, 1) if sent_or_failed else 0.0

    # Average Gemini generation time
    pipe2 = [{"$match": {"gen_ms": {"$gt": 0}}},
             {"$group": {"_id": None, "avg": {"$avg": "$gen_ms"}}}]
    avg_ms = 0
    async for row in emails_col.aggregate(pipe2):
        avg_ms = int(row.get("avg") or 0)
    counts["avg_gen_ms"] = avg_ms

    # Engagement (from delivery.* fields set by Resend webhook)
    delivered = await emails_col.count_documents({"delivery.delivered_at": {"$exists": True}})
    opened = await emails_col.count_documents({"delivery.opened_at": {"$exists": True}})
    clicked = await emails_col.count_documents({"delivery.clicked_at": {"$exists": True}})
    bounced = await emails_col.count_documents({"delivery.bounced_at": {"$exists": True}})
    counts["delivered"] = delivered
    counts["opened"] = opened
    counts["clicked"] = clicked
    counts["bounced"] = bounced
    sent_n = counts["sent"] or 0
    counts["delivery_rate"] = round(delivered * 100.0 / sent_n, 1) if sent_n else 0.0
    counts["open_rate"] = round(opened * 100.0 / delivered, 1) if delivered else 0.0
    counts["click_rate"] = round(clicked * 100.0 / delivered, 1) if delivered else 0.0
    return counts


# ---------- Generation ----------
async def _get_website_summary(website: str) -> Optional[str]:
    """Return cached summary or fetch+cache. Never scrape same URL twice."""
    if not website:
        return None
    cached = await website_cache_col.find_one({"url": website}, {"_id": 0})
    if cached:
        return cached.get("summary") or None
    summary = fetch_website_summary(website)
    await website_cache_col.insert_one({
        "url": website,
        "summary": summary or "",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    })
    return summary


async def _generate_one(doc: dict) -> dict:
    try:
        website_summary = await _get_website_summary(doc.get("website") or "")
        company_context = await get_setting("company_context", read_company_context())
        result = generate_email(
            company_name=doc["company_name"],
            contact_name=doc.get("contact_name", ""),
            contact_email=doc["contact_email"],
            industry=doc.get("industry", ""),
            notes=doc.get("notes", ""),
            website_summary=website_summary,
            company_context=company_context,
        )
        update = {
            "subject": result.email.subject,
            "intro": result.email.intro,
            "status": "generated",
            "stage": "email_generated",
            "error": "",
            "gen_ms": result.elapsed_ms,
        }
    except Exception as e:
        logger.exception("Generation failed for %s", doc.get("id"))
        update = {"status": "failed", "error": f"Gemini: {e}"}
    await emails_col.update_one({"id": doc["id"]}, {"$set": update})
    if update.get("status") == "generated":
        await add_timeline(doc["id"], "email_generated",
                           f"Email generated: {result.email.subject}")
    return update


@api.post("/emails/generate")
async def generate(payload: GenerateIn, _user: str = Depends(require_session)):
    if not allow("generate", 60, 60):
        raise HTTPException(429, "Generation rate limit reached")
    if not payload.ids:
        raise HTTPException(400, "No ids provided")
    results = []
    for _id in payload.ids:
        doc = await emails_col.find_one({"id": _id}, {"_id": 0})
        if not doc:
            results.append({"id": _id, "status": "failed", "error": "Not found"})
            continue
        upd = await _generate_one(doc)
        results.append({"id": _id, **upd})
    return {"results": results}


@api.post("/emails/{email_id}/regenerate")
async def regenerate(email_id: str, _user: str = Depends(require_session)):
    if not allow("generate", 60, 60):
        raise HTTPException(429, "Generation rate limit reached")
    doc = await emails_col.find_one({"id": email_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Email not found")
    upd = await _generate_one(doc)
    if upd.get("status") == "failed":
        raise HTTPException(502, upd.get("error", "Generation failed"))
    return {"id": email_id, **upd}


@api.patch("/emails/{email_id}")
async def update_email(email_id: str, payload: UpdateEmailIn, _user: str = Depends(require_session)):
    upd = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    r = await emails_col.update_one({"id": email_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Email not found")
    return {"ok": True}


@api.delete("/emails/{email_id}")
async def delete_email(email_id: str, _user: str = Depends(require_session)):
    r = await emails_col.delete_one({"id": email_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Email not found")
    return {"ok": True}


# ---------- Sending ----------
@api.post("/emails/send")
async def send(payload: SendIn, _user: str = Depends(require_session)):
    if not payload.ids:
        raise HTTPException(400, "No ids provided")
    if not allow("send", 30, 60):
        raise HTTPException(429, "Send rate limit reached. Try again shortly.")

    daily_limit = int(await get_setting(
        "daily_email_limit", os.environ.get("DAILY_EMAIL_LIMIT", "200")
    ))
    runtime_settings = await get_settings_map()
    results = []
    for _id in payload.ids:
        doc = await emails_col.find_one({"id": _id}, {"_id": 0})
        if not doc:
            results.append({"id": _id, "status": "failed", "error": "Not found"})
            continue
        if doc.get("status") == "sent":
            results.append({"id": _id, "status": "sent", "message_id": doc.get("message_id", "")})
            continue
        if not doc.get("subject") or not doc.get("intro"):
            results.append({"id": _id, "status": "failed", "error": "Email not generated"})
            await emails_col.update_one({"id": _id}, {"$set": {"status": "failed", "error": "Not generated"}})
            continue
        if not await reserve_daily_send(daily_limit):
            await emails_col.update_one({"id": _id}, {"$set": {"status": "failed", "error": "Daily limit reached"}})
            results.append({"id": _id, "status": "failed", "error": "Daily limit reached"})
            continue

        gen = GeneratedEmail(subject=doc["subject"], intro=doc["intro"])
        greeting = build_greeting(doc.get("contact_name", ""), doc["contact_email"])
        html = render_html(greeting, gen, doc["company_name"], runtime_settings)
        plain = render_plain(greeting, gen, doc["company_name"], runtime_settings)
        attachments = await _build_pdf_attachment()

        try:
            msg_id = send_email(
                doc["contact_email"], gen.subject, html, plain,
                attachments=attachments,
                from_email=runtime_settings.get("FROM_EMAIL"),
                from_name=runtime_settings.get("FROM_NAME"),
            )
            now = datetime.now(timezone.utc).isoformat()
            await emails_col.update_one({"id": _id}, {"$set": {
                "status": "sent",
                "stage": "email_sent",
                "message_id": msg_id,
                "sent_at": now,
                "last_contact_at": now,
                "error": "",
            }})
            await add_timeline(_id, "email_sent", f"Email sent to {doc['contact_email']}",
                               f"Subject: {gen.subject}")
            await logs_col.insert_one({
                "id": str(uuid.uuid4()),
                "email_id": _id,
                "company_name": doc["company_name"],
                "contact_email": doc["contact_email"],
                "subject": gen.subject,
                "status": "sent",
                "provider": "resend",
                "message_id": msg_id,
                "gen_ms": doc.get("gen_ms", 0),
                "timestamp": now,
                "error": "",
            })
            results.append({"id": _id, "status": "sent", "message_id": msg_id})
        except Exception as e:
            await release_daily_send()
            logger.exception("Send failed for %s", _id)
            err = str(e)
            now = datetime.now(timezone.utc).isoformat()
            await emails_col.update_one({"id": _id}, {"$set": {"status": "failed", "error": err}})
            await logs_col.insert_one({
                "id": str(uuid.uuid4()),
                "email_id": _id,
                "company_name": doc["company_name"],
                "contact_email": doc["contact_email"],
                "subject": doc.get("subject", ""),
                "status": "failed",
                "provider": "resend",
                "message_id": "",
                "timestamp": now,
                "error": err,
            })
            results.append({"id": _id, "status": "failed", "error": err})

    return {"results": results}


# ---------- Logs ----------
@api.get("/logs")
async def get_logs(q: Optional[str] = None, status: Optional[str] = None,
                   _user: str = Depends(require_session)):
    query: dict = {}
    if status:
        query["status"] = status
    if q:
        query["$or"] = [
            {"company_name": {"$regex": q, "$options": "i"}},
            {"contact_email": {"$regex": q, "$options": "i"}},
            {"subject": {"$regex": q, "$options": "i"}},
        ]
    items = await logs_col.find(query, {"_id": 0}).sort("timestamp", -1).to_list(5000)
    return items


@api.get("/logs/export")
async def export_logs(_user: str = Depends(require_session)):
    items = await logs_col.find({}, {"_id": 0}).sort("timestamp", -1).to_list(10000)
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["timestamp", "company_name", "contact_email", "subject", "status", "provider", "message_id", "error"])
    for it in items:
        writer.writerow([it.get("timestamp"), it.get("company_name"), it.get("contact_email"),
                         it.get("subject"), it.get("status"), it.get("provider"),
                         it.get("message_id"), it.get("error")])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=send_logs.csv"})


# ---------- Settings ----------
@api.get("/settings")
async def get_settings(_user: str = Depends(require_session)):
    saved = await get_settings_map()
    value = lambda key, default="": saved.get(key) or os.environ.get(key, default)
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    pdf_meta: dict = {"present": False, "size": 0}
    storage_meta = await storage_info(PDF_STORAGE_PATH)
    if storage_meta:
        metadata = storage_meta.get("metadata") or {}
        pdf_meta = {
            "present": True,
            "size": int(metadata.get("size") or 0),
            "uploaded_at": storage_meta.get("updated_at") or storage_meta.get("created_at"),
        }
    return {
        "company_context": saved.get("company_context") or read_company_context(),
        "daily_limit": int(saved.get("daily_email_limit") or os.environ.get("DAILY_EMAIL_LIMIT", "200")),
        "from_email": value("FROM_EMAIL"),
        "from_name": value("FROM_NAME"),
        "company_name": value("COMPANY_NAME"),
        "designation": value("DESIGNATION"),
        "phone": value("PHONE"),
        "company_website": value("COMPANY_WEBSITE"),
        "gemini_configured": gemini_ok,
        "resend": resend_status(),
        "pdf": pdf_meta,
        "newsletter_from_email": value("NEWSLETTER_FROM_EMAIL"),
        "newsletter_from_name": value("NEWSLETTER_FROM_NAME"),
        "ai_research_enabled": value("AI_RESEARCH_ENABLED", "true").lower() == "true",
        "send_delay_seconds": int(value("SEND_DELAY_SECONDS", "3")),
    }


@api.put("/settings/context")
async def set_context(payload: ContextIn, _user: str = Depends(require_session)):
    if len(payload.content) > 50_000:
        raise HTTPException(413, "Context too large")
    await set_setting("company_context", payload.content)
    return {"ok": True}


# Keys whose existing value must be preserved if the new value is empty
PROTECTED_IF_EMPTY = {"FROM_EMAIL"}


@api.put("/settings/env")
async def update_env(payload: EnvIn, _user: str = Depends(require_session)):
    provider_keys = {"GEMINI_API_KEY", "RESEND_API_KEY"}
    attempted_provider_keys = provider_keys.intersection(payload.updates)
    if attempted_provider_keys:
        raise HTTPException(
            400,
            "API keys are managed in Vercel environment variables and cannot be changed here",
        )
    bad = [k for k in payload.updates if k not in EDITABLE_ENV_KEYS]
    if bad:
        raise HTTPException(400, f"Not editable: {', '.join(bad)}")
    cleaned: dict[str, str] = {}
    for k, v in payload.updates.items():
        if v is None:
            continue
        val = v.strip()
        if not val and k in PROTECTED_IF_EMPTY:
            continue  # never wipe sensitive keys with an empty value
        cleaned[k] = val
    if not cleaned:
        return {"ok": True, "updated": []}
    for key, value in cleaned.items():
        await set_setting(key, value)
    return {"ok": True, "updated": list(cleaned.keys())}


@api.put("/settings/daily-limit")
async def set_daily_limit(payload: LimitIn, _user: str = Depends(require_session)):
    if payload.daily_limit < 1 or payload.daily_limit > 5000:
        raise HTTPException(400, "Daily limit must be between 1 and 5000")
    await set_setting("daily_email_limit", str(payload.daily_limit))
    return {"ok": True, "daily_limit": payload.daily_limit}


@api.put("/settings/password")
async def change_password(payload: PasswordChangeIn, _user: str = Depends(require_session)):
    if not await verify_password(payload.current_password):
        raise HTTPException(401, "Current password incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "New password must be at least 6 characters")
    await set_password(payload.new_password)
    return {"ok": True}


# ---------- PDF management ----------
@api.post("/settings/pdf")
async def upload_pdf(file: UploadFile = File(...), _user: str = Depends(require_session)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "File must be a .pdf")
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "PDF exceeds 10 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "File does not look like a valid PDF")
    await storage_upload(PDF_STORAGE_PATH, data, "application/pdf")
    return {"ok": True, "size": len(data)}


@api.get("/settings/pdf")
async def download_pdf(_user: str = Depends(require_session)):
    try:
        data = await storage_download(PDF_STORAGE_PATH)
    except Exception:
        raise HTTPException(404, "No PDF uploaded")
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=SDU-Global-Company-Profile.pdf"},
    )


@api.delete("/settings/pdf")
async def delete_pdf(_user: str = Depends(require_session)):
    try:
        await storage_remove(PDF_STORAGE_PATH)
    except Exception:
        pass
    return {"ok": True}


@api.post("/emails/{email_id}/test-send")
async def send_test(email_id: str, _user: str = Depends(require_session)):
    """Send the selected email to the sender's own address for preview."""
    doc = await emails_col.find_one({"id": email_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Email not found")
    if not doc.get("subject") or not doc.get("intro"):
        raise HTTPException(400, "Generate the email first")
    runtime_settings = await get_settings_map()
    own = (runtime_settings.get("FROM_EMAIL") or os.environ.get("FROM_EMAIL", "")).strip()
    if not own:
        raise HTTPException(400, "FROM_EMAIL is not configured")
    gen = GeneratedEmail(subject=f"[TEST] {doc['subject']}", intro=doc["intro"])
    greeting = build_greeting(doc.get("contact_name", ""), doc["contact_email"])
    html = render_html(greeting, gen, doc["company_name"], runtime_settings)
    plain = render_plain(greeting, gen, doc["company_name"], runtime_settings)
    try:
        msg_id = send_email(
            own, gen.subject, html, plain,
            attachments=await _build_pdf_attachment(),
            from_email=own,
            from_name=runtime_settings.get("FROM_NAME"),
        )
        return {"ok": True, "message_id": msg_id, "to": own}
    except Exception as e:
        raise HTTPException(502, f"Send failed: {e}")


# ---------- Resend webhook (delivery tracking) ----------
@app.post("/api/webhooks/resend")
async def resend_webhook(request: Request):
    """Verify and process Resend delivery events using the unmodified request body."""
    secret = os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
    if not secret:
        raise HTTPException(503, "Resend webhook verification is not configured")
    raw = await request.body()
    webhook_id = request.headers.get("svix-id", "")
    headers = {
        "id": webhook_id,
        "timestamp": request.headers.get("svix-timestamp", ""),
        "signature": request.headers.get("svix-signature", ""),
    }
    try:
        resend.Webhooks.verify({
            "payload": raw.decode("utf-8"),
            "headers": headers,
            "webhook_secret": secret,
        })
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(400, f"Invalid webhook: {exc}")

    if await logs_col.find_one({"id": webhook_id}):
        return {"ok": True, "duplicate": True}
    event = (payload.get("type") or payload.get("event") or "").lower()
    data = payload.get("data") or {}
    msg_id = data.get("email_id") or data.get("id") or payload.get("id") or ""
    if not msg_id:
        return {"ok": True}
    # map event → status field
    status_map = {
        "email.sent": "sent", "email.delivered": "delivered",
        "email.delivery_delayed": "delayed", "email.bounced": "bounced",
        "email.complained": "complained", "email.opened": "opened",
        "email.clicked": "clicked", "email.failed": "failed",
    }
    field = status_map.get(event)
    if not field:
        return {"ok": True}
    now = datetime.now(timezone.utc).isoformat()
    upd: dict = {f"delivery.{field}_at": now, "delivery.last_event": event}
    # touch top-level status for terminal states
    if field in ("bounced", "failed", "complained"):
        upd["status"] = "failed"
        upd["error"] = f"resend: {event}"
    await emails_col.update_one({"message_id": msg_id}, {"$set": upd})
    await logs_col.update_many({"message_id": msg_id}, {"$set": {"status": field, "last_event_at": now}})
    await logs_col.insert_one({
        "id": webhook_id, "message_id": msg_id, "event": event,
        "status": field, "timestamp": now,
    })
    return {"ok": True}



app.include_router(api)
app.include_router(crm_router)
app.include_router(newsletter_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
