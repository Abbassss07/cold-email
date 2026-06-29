# SDU Cold Email Outreach

Production-ready cold email outreach console for SDU Global Auditing.

- **Stack:** FastAPI + MongoDB (backend) · React + Tailwind + shadcn UI (frontend)
- **AI:** Google Gemini 2.5 Flash (structured JSON output)
- **Email provider:** Resend
- **Auth:** Single admin password, HTTP-only signed session cookie

---

## Features

- CSV upload with validation (required: `company_name`, `contact_email`; optional: `website`, `notes`)
- Optional homepage enrichment per company (title / description / og tags)
- Gemini 2.5 Flash strict-JSON generation of **subject + intro + body** only (the rest of the email comes from a fixed branded template — keeps voice consistent and tokens cheap)
- Email preview table with **edit, regenerate, delete, checkbox-select**
- Batch send via Resend with stored `message_id` and full log trail
- Logs page with search, status filter, and CSV export
- Settings: company context editor, daily send limit, provider status, password change
- Rate limits + daily quota + max CSV size/rows
- Friendly errors, no crashes

## Project layout

```
/app
├── backend/
│   ├── server.py              FastAPI app & routes
│   ├── auth.py                Session cookies + password verify
│   ├── email_generator.py     Gemini 2.5 Flash structured output
│   ├── email_sender.py        Resend wrapper (swap module to change provider)
│   ├── csv_handler.py         CSV parsing + row validation
│   ├── rate_limiter.py        In-memory rate limit + daily counter
│   ├── company_context.txt    Read every generation
│   └── .env                   See below
├── frontend/                  React app
├── sample_companies.csv       Example CSV
└── README.md
```

## Environment variables (`backend/.env`)

```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="test_database"
CORS_ORIGINS="*"
GEMINI_API_KEY=""                # Get from https://aistudio.google.com/app/apikey
RESEND_API_KEY=""                # Get from https://resend.com/api-keys
FROM_EMAIL="onboarding@resend.dev"
FROM_NAME="SDU Global Auditing"
ADMIN_PASSWORD="admin123"
SECRET_KEY="long-random-string"
DAILY_EMAIL_LIMIT=200
MAX_CSV_ROWS=500
```

`frontend/.env` exposes the backend URL: `REACT_APP_BACKEND_URL=...`.

## Run locally

The platform supervises both processes:

```
sudo supervisorctl restart backend
sudo supervisorctl restart frontend
```

Visit the frontend URL, sign in with `ADMIN_PASSWORD`.

## How to get keys

- **Gemini API key:** https://aistudio.google.com/app/apikey → "Create API key"
- **Resend API key:** https://resend.com/api-keys → make sure your `FROM_EMAIL` domain is verified (or use `onboarding@resend.dev` for testing — recipient must be your own Resend account email)

## Swapping providers

- To replace Gemini: change only `backend/email_generator.py` (keep `generate_email` / `GeneratedEmail` interface)
- To replace Resend: change only `backend/email_sender.py` (keep `send_email(to, subject, html, text) -> message_id`)

## Troubleshooting

- **401 Not authenticated** — sign in again; cookies expire after 7 days
- **Gemini errors** — verify `GEMINI_API_KEY`, model is `gemini-2.5-flash`
- **Resend errors** — verify domain and API key; check Resend dashboard logs
- **CSV errors** — confirm required columns and that emails look like `a@b.c`
