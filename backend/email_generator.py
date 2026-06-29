"""Gemini 2.5 Flash email generator. Generates structured JSON (subject, intro, body)."""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

import requests
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONTEXT_FILE = Path(__file__).parent / "company_context.txt"

GEMINI_MODEL = "gemini-2.5-flash"


class GeneratedEmail(BaseModel):
    """Strict schema returned by Gemini."""
    subject: str = Field(description="Cold email subject line, 5-10 words.")
    intro: str = Field(description="Personalized opening paragraph, 2-3 sentences.")
    body: str = Field(description="Main body paragraph(s) explaining how SDU Global may help, 150-220 words total.")


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def read_company_context() -> str:
    """Read company context from file every time (per spec)."""
    if not CONTEXT_FILE.exists():
        return ""
    return CONTEXT_FILE.read_text(encoding="utf-8")


def write_company_context(content: str) -> None:
    CONTEXT_FILE.write_text(content, encoding="utf-8")


def fetch_website_info(website: str, timeout: int = 6) -> Optional[str]:
    """Best-effort homepage fetch and metadata extraction. Returns None on failure."""
    if not website:
        return None
    url = website.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 SDU-Outreach"})
        if resp.status_code >= 400:
            return None
        html = resp.text[:120_000]  # cap
    except Exception as e:
        logger.info("Website fetch failed for %s: %s", url, e)
        return None

    def _meta(name: str) -> str:
        m = re.search(
            rf'<meta[^>]+(?:name|property)=["\']{name}["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    title_match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    title = title_match.group(1).strip() if title_match else ""
    description = _meta("description") or _meta("og:description")
    site_name = _meta("og:site_name")

    parts = []
    if title:
        parts.append(f"Title: {title}")
    if site_name:
        parts.append(f"Site name: {site_name}")
    if description:
        parts.append(f"Description: {description}")

    return "\n".join(parts) if parts else None


def build_prompt(company_name: str, contact_email: str, notes: str, website_info: Optional[str],
                 company_context: str, from_name: str, from_email: str) -> str:
    return f"""You are writing ONE personalized cold outreach email for SDU Global Auditing.

== FIRM CONTEXT (authoritative; do not contradict) ==
{company_context}

== TARGET COMPANY ==
Company name: {company_name}
Recipient email: {contact_email}
Notes about the company: {notes or "(none)"}
Website info (auto-extracted, may be empty):
{website_info or "(none available)"}

== SENDER ==
From name: {from_name}
From email: {from_email}

== TASK ==
Return STRICT JSON with EXACTLY these three keys:
  - "subject": 5-10 words, specific, no clickbait, no emojis.
  - "intro": 2-3 sentences that reference the target company naturally. Avoid every cliché listed in the firm context.
  - "body": 150-220 words. Briefly introduce SDU Global, highlight 1-2 relevant services for this company, and close with the call to action from the firm context.

Do NOT include greetings ("Dear..."), signatures, or sign-offs in any field. Those are added by the template.
Do NOT invent facts about the company. If you have no info, write a professional generic introduction.
Output JSON only, nothing else.
"""


def generate_email(company_name: str, contact_email: str, notes: str, website: Optional[str]) -> GeneratedEmail:
    """Generate a cold email using Gemini 2.5 Flash with structured output."""
    company_context = read_company_context()
    from_name = os.environ.get("FROM_NAME", "SDU Global Auditing")
    from_email = os.environ.get("FROM_EMAIL", "")
    website_info = fetch_website_info(website) if website else None

    prompt = build_prompt(company_name, contact_email, notes or "", website_info,
                          company_context, from_name, from_email)

    client = _get_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeneratedEmail,
            temperature=0.7,
        ),
    )

    text = (response.text or "").strip()
    # Defensive JSON parse + validation
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # try to extract JSON block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise RuntimeError(f"Gemini returned non-JSON content: {text[:200]}")
        data = json.loads(m.group(0))

    email = GeneratedEmail(**data)
    # Trim safeties
    email.subject = email.subject.strip().strip('"').strip("'")
    email.intro = email.intro.strip()
    email.body = email.body.strip()
    return email


def render_html(recipient_name: str, generated: GeneratedEmail) -> str:
    """Wrap Gemini output in a fixed branded HTML template."""
    from_name = os.environ.get("FROM_NAME", "SDU Global Auditing")
    from_email = os.environ.get("FROM_EMAIL", "")

    intro_html = _paragraphs(generated.intro)
    body_html = _paragraphs(generated.body)
    greeting = f"Dear {recipient_name}," if recipient_name else "Hello,"

    return f"""<!doctype html>
<html><body style="font-family:Arial,Helvetica,sans-serif;color:#0f172a;line-height:1.6;font-size:15px;max-width:640px;margin:0 auto;padding:24px;">
<p>{greeting}</p>
{intro_html}
{body_html}
<p>Best regards,<br/>
<strong>{from_name}</strong><br/>
SDU Global Auditing<br/>
Dubai, UAE<br/>
<a href="mailto:{from_email}" style="color:#2563EB;">{from_email}</a></p>
</body></html>"""


def render_plain(recipient_name: str, generated: GeneratedEmail) -> str:
    from_name = os.environ.get("FROM_NAME", "SDU Global Auditing")
    from_email = os.environ.get("FROM_EMAIL", "")
    greeting = f"Dear {recipient_name}," if recipient_name else "Hello,"
    return (
        f"{greeting}\n\n"
        f"{generated.intro}\n\n"
        f"{generated.body}\n\n"
        f"Best regards,\n{from_name}\n"
        f"SDU Global Auditing\nDubai, UAE\n{from_email}\n"
    )


def _paragraphs(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not parts:
        return f"<p>{text}</p>"
    return "".join(f"<p>{p}</p>" for p in parts)
