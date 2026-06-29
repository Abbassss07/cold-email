"""SDU Global Cold Email Outreach – FastAPI backend."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from starlette.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from auth import (  # noqa: E402
    clear_session_cookie,
    create_session_cookie,
    require_session,
    verify_password,
)
from csv_handler import parse_csv  # noqa: E402
from email_generator import (  # noqa: E402
    GeneratedEmail,
    generate_email,
    read_company_context,
    render_html,
    render_plain,
    write_company_context,
)
from email_sender import check_status as resend_status, send_email  # noqa: E402
from rate_limiter import allow, daily_count, daily_increment  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("sdu")

# ---------- DB ----------
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]
emails_col = db.cold_emails
logs_col = db.send_logs
settings_col = db.settings

# ---------- PDF attachment ----------
PDF_PATH = ROOT_DIR / "company_profile.pdf"


def _build_pdf_attachment() -> list:
    """Returns Resend-compatible attachments list (base64) if PDF exists, else []."""
    if not PDF_PATH.exists():
        return []
    import base64
    content = base64.b64encode(PDF_PATH.read_bytes()).decode("ascii")
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
    website: str = ""
    notes: str = ""
    subject: str = ""
    intro: str = ""
    status: str = "pending"  # pending|generated|sending|sent|failed
    provider: str = "resend"
    message_id: str = ""
    error: str = ""
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


# ---------- Auth ----------
@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    if not allow("login", 10, 60):
        raise HTTPException(429, "Too many login attempts. Try again shortly.")
    if not verify_password(payload.password):
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
            website=row.get("website", ""),
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
    counts["daily_sent"] = daily_count("sent")
    counts["daily_limit"] = int(os.environ.get("DAILY_EMAIL_LIMIT", "200"))
    return counts


# ---------- Generation ----------
async def _generate_one(doc: dict) -> dict:
    try:
        gen = generate_email(
            company_name=doc["company_name"],
            contact_email=doc["contact_email"],
            notes=doc.get("notes", ""),
            website=doc.get("website") or None,
        )
        update = {
            "subject": gen.subject,
            "intro": gen.intro,
            "status": "generated",
            "error": "",
        }
    except Exception as e:
        logger.exception("Generation failed for %s", doc.get("id"))
        update = {"status": "failed", "error": f"Gemini: {e}"}
    await emails_col.update_one({"id": doc["id"]}, {"$set": update})
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

    daily_limit = int(os.environ.get("DAILY_EMAIL_LIMIT", "200"))
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
        if daily_count("sent") >= daily_limit:
            await emails_col.update_one({"id": _id}, {"$set": {"status": "failed", "error": "Daily limit reached"}})
            results.append({"id": _id, "status": "failed", "error": "Daily limit reached"})
            continue

        gen = GeneratedEmail(subject=doc["subject"], intro=doc["intro"])
        recipient_name = doc["company_name"]
        html = render_html(recipient_name, gen)
        plain = render_plain(recipient_name, gen)
        attachments = _build_pdf_attachment()

        try:
            msg_id = send_email(doc["contact_email"], gen.subject, html, plain,
                                attachments=attachments)
            now = datetime.now(timezone.utc).isoformat()
            await emails_col.update_one({"id": _id}, {"$set": {
                "status": "sent",
                "message_id": msg_id,
                "sent_at": now,
                "error": "",
            }})
            await logs_col.insert_one({
                "id": str(uuid.uuid4()),
                "email_id": _id,
                "company_name": doc["company_name"],
                "contact_email": doc["contact_email"],
                "subject": gen.subject,
                "status": "sent",
                "provider": "resend",
                "message_id": msg_id,
                "timestamp": now,
                "error": "",
            })
            daily_increment("sent")
            results.append({"id": _id, "status": "sent", "message_id": msg_id})
        except Exception as e:
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
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    pdf_meta: dict = {"present": False, "size": 0}
    if PDF_PATH.exists():
        st = PDF_PATH.stat()
        pdf_meta = {
            "present": True,
            "size": st.st_size,
            "uploaded_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
        }
    return {
        "company_context": read_company_context(),
        "daily_limit": int(os.environ.get("DAILY_EMAIL_LIMIT", "200")),
        "from_email": os.environ.get("FROM_EMAIL", ""),
        "from_name": os.environ.get("FROM_NAME", ""),
        "gemini_configured": gemini_ok,
        "resend": resend_status(),
        "pdf": pdf_meta,
    }


@api.put("/settings/context")
async def set_context(payload: ContextIn, _user: str = Depends(require_session)):
    if len(payload.content) > 50_000:
        raise HTTPException(413, "Context too large")
    write_company_context(payload.content)
    return {"ok": True}


@api.put("/settings/daily-limit")
async def set_daily_limit(payload: LimitIn, _user: str = Depends(require_session)):
    if payload.daily_limit < 1 or payload.daily_limit > 5000:
        raise HTTPException(400, "Daily limit must be between 1 and 5000")
    os.environ["DAILY_EMAIL_LIMIT"] = str(payload.daily_limit)
    return {"ok": True, "daily_limit": payload.daily_limit}


@api.put("/settings/password")
async def change_password(payload: PasswordChangeIn, _user: str = Depends(require_session)):
    if not verify_password(payload.current_password):
        raise HTTPException(401, "Current password incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(400, "New password must be at least 6 characters")
    # update .env in place
    env_path = ROOT_DIR / ".env"
    lines = env_path.read_text().splitlines()
    new_lines = []
    replaced = False
    for ln in lines:
        if ln.startswith("ADMIN_PASSWORD="):
            new_lines.append(f'ADMIN_PASSWORD="{payload.new_password}"')
            replaced = True
        else:
            new_lines.append(ln)
    if not replaced:
        new_lines.append(f'ADMIN_PASSWORD="{payload.new_password}"')
    env_path.write_text("\n".join(new_lines) + "\n")
    os.environ["ADMIN_PASSWORD"] = payload.new_password
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
    PDF_PATH.write_bytes(data)
    return {"ok": True, "size": len(data)}


@api.get("/settings/pdf")
async def download_pdf(_user: str = Depends(require_session)):
    if not PDF_PATH.exists():
        raise HTTPException(404, "No PDF uploaded")
    return FileResponse(PDF_PATH, media_type="application/pdf",
                        filename="SDU-Global-Company-Profile.pdf")


@api.delete("/settings/pdf")
async def delete_pdf(_user: str = Depends(require_session)):
    if PDF_PATH.exists():
        PDF_PATH.unlink()
    return {"ok": True}


# ---------- Wire up ----------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
