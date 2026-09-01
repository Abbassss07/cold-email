# SDU Cold Email Outreach

Cold-email and newsletter outreach console for SDU Global Auditing.

- **Frontend:** Create React App, React Router, Tailwind, shadcn/Radix UI
- **Backend:** FastAPI on Vercel's Python runtime
- **Database and files:** Supabase Postgres and private Supabase Storage
- **Email:** Resend
- **AI:** Google Gemini 2.5 Flash
- **Auth:** Single-admin password with a signed HTTP-only session cookie

## Repository layout

```text
backend/                 FastAPI API and Python dependencies
frontend/                Create React App frontend
supabase/migrations/     Postgres schema, RLS, quota functions, Storage bucket
```

## Supabase setup

Create a new Supabase project, then apply the migration in `supabase/migrations`:

```bash
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db push
```

The migration creates:

- leads/cold emails
- send and delivery logs
- website-enrichment cache
- CRM tasks, meetings, and timeline
- contact lists and newsletter campaigns
- durable application settings and admin password override
- atomic daily send counts
- a private `app-files` Storage bucket for the company-profile PDF

All public-schema tables have RLS enabled. Browser roles are explicitly denied; only the backend service-role client accesses them. Never expose `SUPABASE_SERVICE_ROLE_KEY` to the React frontend.

## Local development

Copy the environment templates and fill in real values:

```bash
copy backend\.env.example backend\.env
copy frontend\.env.example frontend\.env
```

Backend:

```bash
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\uvicorn server:app --reload --port 8000
```

Frontend, in another terminal:

```bash
cd frontend
npm ci
npm start
```

## Vercel deployment

This repository deploys as one Vercel Services project using the root `vercel.json`:

- `frontend/`: Create React App service at `/`
- `backend/`: FastAPI service at `/api`
- Python: 3.12 from `backend/.python-version`
- Frontend build/output: `npm run build` / `build`
- API requests remain same-origin, so no separate frontend backend URL is needed in production

Select the **Services** application preset when importing the repository and add the backend variables from `backend/.env.example` to the project.

## Resend webhook

After the backend is deployed, create a Resend webhook pointing to:

```text
https://YOUR-PROJECT-DOMAIN/api/webhooks/resend
```

Subscribe to the email delivery events you need, then put its signing secret in `RESEND_WEBHOOK_SECRET`. Incoming events are signature-verified and de-duplicated using the Svix event ID.

## Security notes

- Replace the placeholder `ADMIN_PASSWORD` and `SECRET_KEY` values before deployment.
- `SECRET_KEY` must be at least 16 characters; use a long random value.
- Use a verified Resend sending domain for `FROM_EMAIL`.
- The admin password can be changed in Settings; the changed bcrypt hash is stored in Supabase. `ADMIN_PASSWORD` remains the initial/bootstrap password.
- API keys are deliberately not editable in the browser. Manage them in Vercel.
