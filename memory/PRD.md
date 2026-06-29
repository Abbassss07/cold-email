# Cold Email Outreach – PRD

## Original problem statement
Build a production-quality cold email outreach web app for SDU Global Auditing (Dubai). Upload CSV, generate personalized emails with Gemini 2.5 Flash + company_context.txt (+ optional website enrichment), preview/edit/regenerate/delete, send via Resend, log every send. Single admin auth with HTTP-only session cookies.

## Stack chosen
React + FastAPI + MongoDB. Gemini 2.5 Flash (user's own key). Resend (user provides key later).

## Implemented (2026-02)
- Auth: itsdangerous-signed HTTP-only cookie, constant-time password compare, rate-limited login
- CSV upload + validation (required/optional cols, email format, max rows, skipped report)
- Gemini 2.5 Flash structured JSON output (subject/intro/body) wrapped in branded HTML+text template
- Optional homepage scrape (title / meta description / og:site_name) feeds into prompt
- Per-row generate, regenerate, edit, delete; batch generate + send
- Resend integration storing message_id; full logs collection
- Logs page: search, status filter, CSV export
- Settings: provider status, company context editor (persisted to file), daily limit, password change (rewrites .env)
- Rate limits (login, generate, send), daily send counter
- Polished Manrope UI; shadcn dialog used for edit; Sonner toasts; progress bar; empty/error states

## Backlog
- P0 (provided keys are required to fully run end-to-end): add real GEMINI_API_KEY + RESEND_API_KEY
- P1: per-recipient personalization tokens (e.g. {{first_name}}), reply tracking via Resend inbound, schedule send, follow-up sequences
- P1: replace Motor with PyMongo async (motor deprecated)
- P2: campaigns, A/B variants, analytics charts, multi-user roles
