"""CRM extensions: leads pipeline, tasks, meetings, timeline. Additive router."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_session

crm = APIRouter(prefix="/api", tags=["crm"])

STAGES = [
    "new_lead", "email_generated", "email_sent", "replied",
    "meeting_scheduled", "proposal_sent", "negotiation",
    "won", "lost", "archived",
]

SERVICES = [
    "external_audit", "internal_audit", "accounting_bookkeeping",
    "vat_registration", "vat_filing", "corporate_tax",
    "tax_advisory", "e_invoicing", "payroll",
    "business_setup", "risk_advisory", "other",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- Models ----------
class LeadUpdateIn(BaseModel):
    stage: Optional[str] = None
    country: Optional[str] = None
    phone: Optional[str] = None
    services: Optional[list[str]] = None
    internal_notes: Optional[str] = None


class TaskIn(BaseModel):
    lead_id: Optional[str] = None
    title: str
    due_date: Optional[str] = None
    notes: str = ""


class TaskUpdateIn(BaseModel):
    title: Optional[str] = None
    due_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None  # pending|completed


class MeetingIn(BaseModel):
    lead_id: str
    date: str
    time: str = ""
    outcome: str = ""
    notes: str = ""
    next_action: str = ""


class TimelineIn(BaseModel):
    lead_id: str
    kind: str
    title: str
    detail: str = ""


# ---------- Wiring: dependency-injected DB collections ----------
_db = {"leads": None, "tasks": None, "meetings": None, "timeline": None, "logs": None}


def bind_db(leads_col, tasks_col, meetings_col, timeline_col, logs_col):
    _db["leads"] = leads_col
    _db["tasks"] = tasks_col
    _db["meetings"] = meetings_col
    _db["timeline"] = timeline_col
    _db["logs"] = logs_col


async def add_timeline(lead_id: str, kind: str, title: str, detail: str = ""):
    if _db["timeline"] is None:
        return
    await _db["timeline"].insert_one({
        "id": str(uuid.uuid4()),
        "lead_id": lead_id,
        "kind": kind,
        "title": title,
        "detail": detail,
        "at": _now(),
    })


# ---------- Meta ----------
@crm.get("/crm/meta")
async def crm_meta(_u: str = Depends(require_session)):
    return {"stages": STAGES, "services": SERVICES}


# ---------- Leads ----------
@crm.get("/leads/{lead_id}")
async def get_lead(lead_id: str, _u: str = Depends(require_session)):
    lead = await _db["leads"].find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")
    lead.setdefault("stage", "new_lead")
    lead.setdefault("services", [])
    lead.setdefault("internal_notes", "")
    lead.setdefault("country", "")
    lead.setdefault("phone", "")
    return lead


@crm.patch("/leads/{lead_id}")
async def update_lead(lead_id: str, payload: LeadUpdateIn, _u: str = Depends(require_session)):
    upd = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if "stage" in upd and upd["stage"] not in STAGES:
        raise HTTPException(400, f"Invalid stage. Allowed: {', '.join(STAGES)}")
    if "services" in upd:
        bad = [s for s in upd["services"] if s not in SERVICES]
        if bad:
            raise HTTPException(400, f"Invalid services: {', '.join(bad)}")
    old = await _db["leads"].find_one({"id": lead_id})
    if not old:
        raise HTTPException(404, "Lead not found")
    r = await _db["leads"].update_one({"id": lead_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Lead not found")
    if "stage" in upd and upd["stage"] != old.get("stage"):
        await add_timeline(lead_id, "stage_change", f"Stage → {upd['stage'].replace('_', ' ').title()}")
    return {"ok": True}


@crm.get("/leads/{lead_id}/timeline")
async def lead_timeline(lead_id: str, _u: str = Depends(require_session)):
    items = await _db["timeline"].find({"lead_id": lead_id}, {"_id": 0}).sort("at", -1).to_list(500)
    return items


@crm.post("/leads/{lead_id}/timeline")
async def add_timeline_entry(lead_id: str, payload: TimelineIn, _u: str = Depends(require_session)):
    await add_timeline(lead_id, payload.kind, payload.title, payload.detail)
    return {"ok": True}


# ---------- Pipeline ----------
@crm.get("/pipeline")
async def pipeline(_u: str = Depends(require_session)):
    counts = {s: 0 for s in STAGES}
    async for row in _db["leads"].aggregate([{"$group": {"_id": "$stage", "n": {"$sum": 1}}}]):
        s = row["_id"] or "new_lead"
        if s in counts:
            counts[s] = row["n"]
    return {"stages": STAGES, "counts": counts}


# ---------- Tasks ----------
@crm.get("/tasks")
async def list_tasks(lead_id: Optional[str] = None, status: Optional[str] = None,
                     _u: str = Depends(require_session)):
    q: dict = {}
    if lead_id:
        q["lead_id"] = lead_id
    if status:
        q["status"] = status
    items = await _db["tasks"].find(q, {"_id": 0}).sort("due_date", 1).to_list(500)
    today = datetime.now(timezone.utc).date().isoformat()
    for it in items:
        if it.get("status") == "pending" and it.get("due_date") and it["due_date"] < today:
            it["status"] = "overdue"
    return items


@crm.post("/tasks")
async def create_task(payload: TaskIn, _u: str = Depends(require_session)):
    doc = {
        "id": str(uuid.uuid4()),
        "lead_id": payload.lead_id or "",
        "title": payload.title,
        "due_date": payload.due_date or "",
        "notes": payload.notes,
        "status": "pending",
        "created_at": _now(),
    }
    await _db["tasks"].insert_one(doc)
    if payload.lead_id:
        await add_timeline(payload.lead_id, "task_created", f"Task: {payload.title}",
                           f"Due {payload.due_date or 'n/a'}")
    doc.pop("_id", None)
    return doc


@crm.patch("/tasks/{task_id}")
async def update_task(task_id: str, payload: TaskUpdateIn, _u: str = Depends(require_session)):
    upd = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not upd:
        raise HTTPException(400, "Nothing to update")
    r = await _db["tasks"].update_one({"id": task_id}, {"$set": upd})
    if r.matched_count == 0:
        raise HTTPException(404, "Task not found")
    if upd.get("status") == "completed":
        t = await _db["tasks"].find_one({"id": task_id}, {"_id": 0})
        if t and t.get("lead_id"):
            await add_timeline(t["lead_id"], "task_completed", f"Task completed: {t.get('title', '')}")
    return {"ok": True}


@crm.delete("/tasks/{task_id}")
async def delete_task(task_id: str, _u: str = Depends(require_session)):
    r = await _db["tasks"].delete_one({"id": task_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Task not found")
    return {"ok": True}


# ---------- Meetings ----------
@crm.get("/meetings")
async def list_meetings(lead_id: Optional[str] = None, _u: str = Depends(require_session)):
    q = {"lead_id": lead_id} if lead_id else {}
    items = await _db["meetings"].find(q, {"_id": 0}).sort("date", -1).to_list(500)
    return items


@crm.post("/meetings")
async def create_meeting(payload: MeetingIn, _u: str = Depends(require_session)):
    doc = payload.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["created_at"] = _now()
    await _db["meetings"].insert_one(doc)
    await add_timeline(payload.lead_id, "meeting",
                       f"Meeting {payload.date} {payload.time}".strip(),
                       payload.outcome or payload.notes)
    # Auto-advance stage
    lead = await _db["leads"].find_one({"id": payload.lead_id})
    if lead and lead.get("stage") in ("new_lead", "email_generated", "email_sent", "replied"):
        await _db["leads"].update_one({"id": payload.lead_id},
                                       {"$set": {"stage": "meeting_scheduled"}})
    doc.pop("_id", None)
    return doc


@crm.delete("/meetings/{meeting_id}")
async def delete_meeting(meeting_id: str, _u: str = Depends(require_session)):
    r = await _db["meetings"].delete_one({"id": meeting_id})
    if r.deleted_count == 0:
        raise HTTPException(404, "Meeting not found")
    return {"ok": True}


# ---------- Dashboard summary ----------
@crm.get("/dashboard/summary")
async def dashboard_summary(_u: str = Depends(require_session)):
    total_leads = await _db["leads"].count_documents({})
    won = await _db["leads"].count_documents({"stage": "won"})
    lost = await _db["leads"].count_documents({"stage": "lost"})
    replied = await _db["leads"].count_documents({"stage": {"$in": ["replied", "meeting_scheduled", "proposal_sent", "negotiation", "won"]}})
    sent = await _db["leads"].count_documents({"stage": {"$in": ["email_sent", "replied", "meeting_scheduled", "proposal_sent", "negotiation", "won", "lost"]}})
    meetings = await _db["meetings"].count_documents({})
    reply_rate = round(replied * 100.0 / sent, 1) if sent else 0.0

    today = datetime.now(timezone.utc).date().isoformat()
    upcoming = await _db["tasks"].find(
        {"status": {"$ne": "completed"}, "due_date": {"$gte": today}},
        {"_id": 0}
    ).sort("due_date", 1).limit(5).to_list(5)
    recent = await _db["timeline"].find({}, {"_id": 0}).sort("at", -1).limit(10).to_list(10)

    return {
        "total_leads": total_leads, "sent": sent, "replied": replied,
        "meetings": meetings, "won": won, "lost": lost, "reply_rate": reply_rate,
        "upcoming_tasks": upcoming, "recent_activity": recent,
    }
