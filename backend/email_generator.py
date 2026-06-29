"""Gemini 2.5 Flash – generates ONLY subject + intro. Cost-optimized."""
from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional

import requests
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONTEXT_FILE = Path(__file__).parent / "company_context.txt"
BODY_HTML_FILE = Path(__file__).parent / "email_body_template.html"
BODY_TEXT_FILE = Path(__file__).parent / "email_body_template.txt"

GEMINI_MODEL = "gemini-2.5-flash"
INTRO_MIN_WORDS = 40
INTRO_MAX_WORDS = 70


class GeneratedEmail(BaseModel):
    """Strict schema. Greeting/signature/body are NEVER AI-generated."""
    subject: str = Field(description="Cold email subject, 5-10 words, no emojis.")
    intro: str = Field(description=f"Personalized opening paragraph, {INTRO_MIN_WORDS}-{INTRO_MAX_WORDS} words. No greeting line, no signature.")


class GenerationResult(BaseModel):
    email: GeneratedEmail
    elapsed_ms: int


def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    return genai.Client(api_key=api_key)


def read_company_context() -> str:
    return CONTEXT_FILE.read_text(encoding="utf-8") if CONTEXT_FILE.exists() else ""


def write_company_context(content: str) -> None:
    CONTEXT_FILE.write_text(content, encoding="utf-8")


def read_body_html() -> str:
    return BODY_HTML_FILE.read_text(encoding="utf-8") if BODY_HTML_FILE.exists() else ""


def read_body_text() -> str:
    return BODY_TEXT_FILE.read_text(encoding="utf-8") if BODY_TEXT_FILE.exists() else ""


def fetch_website_summary(website: str, timeout: int = 6) -> Optional[str]:
    """Best-effort homepage scrape → short summary (max 300 words). None on failure."""
    if not website:
        return None
    url = website.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0 SDU-Outreach"})
        if resp.status_code >= 400:
            return None
        html = resp.text[:120_000]
    except Exception as e:
        logger.info("Website fetch failed for %s: %s", url, e)
        return None

    def _meta(name: str) -> str:
        m = re.search(
            rf'<meta[^>]+(?:name|property)=["\']{name}["\'][^>]+content=["\']([^"\']+)["\']',
            html, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.IGNORECASE)
    title = title_m.group(1).strip() if title_m else ""
    description = _meta("description") or _meta("og:description")
    site_name = _meta("og:site_name")
    locality = _meta("og:locality") or _meta("geo.placename")

    parts = []
    if title: parts.append(f"Title: {title}")
    if site_name: parts.append(f"Site name: {site_name}")
    if description: parts.append(f"Description: {description}")
    if locality: parts.append(f"Location: {locality}")
    summary = "\n".join(parts)
    if not summary:
        return None
    # cap at 300 words
    words = summary.split()
    if len(words) > 300:
        summary = " ".join(words[:300])
    return summary


def _build_prompt(*, company_name: str, contact_name: str, contact_email: str,
                  industry: str, notes: str, website_summary: Optional[str],
                  company_context: str) -> str:
    """Compact, structured prompt — minimal tokens."""
    recipient_known = bool(contact_name.strip())
    recipient_line = (
        f"Recipient: {contact_name} (known individual at the company)"
        if recipient_known
        else "Recipient: unknown — address them as a representative of the company; "
             "use 'your organization' / 'your business' / 'your team', NEVER 'leaders like yourself'"
    )

    return f"""You write ONE personalized cold-email INTRO for an auditing firm. Output JSON only.

{recipient_line}
Company: {company_name}
Industry: {industry or "(unspecified)"}
Notes: {notes or "(none)"}
Website summary: {website_summary or "(not available)"}

Firm context (do not contradict):
{company_context}

Return JSON: {{"subject":"...","intro":"..."}}
- subject: 5-10 words, specific, no clickbait, no emojis.
- intro: ONE paragraph, {INTRO_MIN_WORDS}-{INTRO_MAX_WORDS} words. Naturally reference the company / industry. Do NOT describe our services, do NOT add a CTA, do NOT include a greeting or sign-off. Avoid clichés ("I hope this email finds you well", "in today's fast-paced...").
"""


def _truncate_words(text: str, limit: int) -> str:
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(",.;:") + "."


def generate_email(*, company_name: str, contact_name: str, contact_email: str,
                   industry: str = "", notes: str = "",
                   website_summary: Optional[str] = None,
                   max_retries: int = 2) -> GenerationResult:
    """Generate subject + intro with up to 2 additional retries on transient failures."""
    company_context = read_company_context()
    prompt = _build_prompt(
        company_name=company_name, contact_name=contact_name, contact_email=contact_email,
        industry=industry, notes=notes, website_summary=website_summary,
        company_context=company_context,
    )

    client = _get_client()
    last_err: Optional[Exception] = None
    started = time.time()
    for attempt in range(max_retries + 1):
        try:
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
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                m = re.search(r"\{.*\}", text, re.DOTALL)
                if not m:
                    raise RuntimeError(f"Non-JSON response: {text[:200]}")
                data = json.loads(m.group(0))
            email = GeneratedEmail(**data)
            email.subject = email.subject.strip().strip('"').strip("'")
            email.intro = _truncate_words(email.intro.strip(), INTRO_MAX_WORDS)
            elapsed_ms = int((time.time() - started) * 1000)
            return GenerationResult(email=email, elapsed_ms=elapsed_ms)
        except Exception as e:
            last_err = e
            logger.warning("Gemini attempt %d failed: %s", attempt + 1, e)
            if attempt < max_retries:
                time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(f"Gemini failed after {max_retries + 1} attempts: {last_err}")


def _paragraphs(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not parts:
        return f"<p>{text}</p>"
    return "".join(f"<p>{p}</p>" for p in parts)


def _render(template: str, mapping: dict) -> str:
    for k, v in mapping.items():
        template = template.replace("{{" + k + "}}", v)
    return template


def _template_vars(greeting: str, intro_text: str, company_name_recipient: str) -> dict:
    return {
        "greeting": greeting,
        "intro": intro_text,
        "company_name": os.environ.get("COMPANY_NAME", "SDU Global Auditing"),
        "from_name": os.environ.get("FROM_NAME", "SDU Global Auditing"),
        "designation": os.environ.get("DESIGNATION", "Business Advisory"),
        "phone": os.environ.get("PHONE", ""),
        "website": os.environ.get("COMPANY_WEBSITE", ""),
        "from_email": os.environ.get("FROM_EMAIL", ""),
        "recipient_company": company_name_recipient,
    }


def render_html(greeting: str, generated: GeneratedEmail, recipient_company: str) -> str:
    tpl = read_body_html()
    intro_html = _paragraphs(generated.intro)
    # When substituting intro into HTML template, replace {{intro}} as raw paragraph(s)
    mapping = _template_vars(greeting, "__INTRO_PH__", recipient_company)
    rendered = _render(tpl, mapping)
    return rendered.replace("__INTRO_PH__", intro_html)


def render_plain(greeting: str, generated: GeneratedEmail, recipient_company: str) -> str:
    tpl = read_body_text()
    mapping = _template_vars(greeting, generated.intro, recipient_company)
    return _render(tpl, mapping)
