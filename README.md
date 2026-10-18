# JobTrack AI

A self-hosted job search automation tool: connect free job-board APIs, track
applications through a kanban board, and send approval-gated, humble-professional
follow-up emails from your own inbox — all with multi-user logins and a super
admin account.

## What's included

- **Backend** (FastAPI + Postgres): auth, job connectors, application tracking,
  follow-up drafting/approval/sending, dashboard stats, admin user management.
- **Frontend** (Next.js + Tailwind): responsive dashboard, job search, kanban
  tracking board, follow-up review queue, settings.
- **4 job-source connectors out of the box**: Adzuna, Greenhouse (public boards,
  no key needed), Lever (public postings, no key needed), JSearch/RapidAPI.
- **Follow-up scheduler**: runs every 5 minutes, sends any follow-up you've
  approved once its suggested send time arrives. Nothing sends without your
  explicit approval first.

## Design choice worth knowing

This tool does **not** attempt unattended auto-apply against LinkedIn/Indeed's
own application forms — that violates their Terms of Service and is a common
cause of account bans and recruiter blacklisting. Instead, tracked applications
get a one-tap "apply link" to the verified posting, with your tracking already
set up. It's the safe version of auto-apply. (Greenhouse/Lever postings link
directly to each company's own application page.)

---

## 1. Deploy on your homelab server

Requirements: Docker + Docker Compose installed on the server.

```bash
git clone <wherever you push this> jobtrack-ai
cd jobtrack-ai
cp .env.example .env
```

Edit `.env`:

- `SUPER_ADMIN_EMAIL` — the email you'll register with to become super admin.
- `JWT_SECRET` — generate with `openssl rand -hex 32`.
- `SECRETS_ENCRYPTION_KEY` — generate with:
  ```bash
  python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
  ```
- `NEXT_PUBLIC_API_URL` — set this to how your friends' browsers will reach the
  backend. On your Tailscale network this is typically your server's Tailscale
  IP, e.g. `http://100.64.0.2:8000`.

Then:

```bash
docker compose up -d --build
```

- Backend: `http://<server>:8000` (interactive API docs at `/docs`)
- Frontend: `http://<server>:3000`

Since your homelab already runs Tailscale, the simplest way to let friends in
without exposing anything to the public internet is to add them to your
Tailscale network (or a shared Tailscale ACL group) and just hand out the
Tailscale IP + port 3000.

Register with `SUPER_ADMIN_EMAIL` first — that account automatically becomes
super admin. Every other email that registers afterward gets a normal account.

## 2. Connect job sources (per user, in Settings)

- **Adzuna** — free key at https://developer.adzuna.com/
- **JSearch** — free tier at https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
- **Greenhouse / Lever** — no key needed. Just list the company board/site
  names you want to track (e.g. a company's Greenhouse board token is the
  slug in `boards.greenhouse.io/<token>`).

## 3. Connect email for follow-ups AND inbox analysis (per user, in Settings)

Use an **app password**, not your normal login password:

- Gmail: Google Account → Security → 2-Step Verification → App passwords
- Outlook: account security settings → App passwords

SMTP host/port defaults are pre-filled for Gmail (`smtp.gmail.com:587`) —
change them if you use a different provider. The same credentials are reused
for IMAP (reading your inbox); the IMAP host is auto-detected for Gmail,
Outlook, and Yahoo — enter it manually for anything else.

Turn on **"Analyze my inbox for job replies & alerts"** to have the app read
job-related mail — Naukri, LinkedIn, Indeed, Shine, application confirmations,
interview invites, rejections, offers, or a company's own reply — and surface
it on your dashboard automatically. This is **read-only**: nothing is ever
sent from your inbox, and analysis runs on a conservative interval (every
`INBOX_POLL_INTERVAL_MINUTES`, default 25) processing at most
`INBOX_MAX_EMAILS_PER_POLL` new emails per check, specifically so it stays
light on small servers.

Classification uses Google's Gemini API — set `GOOGLE_AI_API_KEY` in `.env`
(free key at https://aistudio.google.com/apikey). Leave it blank and inbox
analysis simply does nothing (no errors) — everything else in the app works
fine without it.

**Why not a direct Naukri/LinkedIn/Indeed API?** None of them offer a public
API for this anymore (LinkedIn actively blocks scraping and enforces this
aggressively). Reading your own inbox — which is what those platforms
already email you, with your consent — is the legitimate way to get that
signal without violating anyone's Terms of Service.

## 4. Using it

1. **Find Jobs** — search across every source you've connected, track any
   result with one tap. Found something on Naukri, LinkedIn, Indeed, or a
   company site instead? Use **Add manually** on the same page — paste in
   the title/company/link and it's tracked exactly like a searched result.
2. **Applications** — kanban board (Saved → Applied → Interviewing → Offer /
   Rejected / Ghosted). Add a recruiter/contact email and resume version used
   on each card.
3. **Follow-ups** — generate a draft from a prebuilt template
   (check-in / interview thank-you / gentle nudge), review and edit it, then
   either **Approve** (sends automatically at the suggested time — Tue/Wed/Thu
   mornings tend to get the best response rates) or **Send now**.
4. **Dashboard** — response rate, pipeline breakdown, pending follow-ups, and
   an **Inbox activity** feed of everything detected in your email: replies
   matched to a tracked application, and job-alert digests with a one-tap
   "Track" button per posting found inside them.

## Local development (without Docker)

Backend:
```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:///./dev.db"
export SECRETS_ENCRYPTION_KEY="<generate as above>"
export SUPER_ADMIN_EMAIL="you@example.com"
export JWT_SECRET="dev-secret"
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
npm run dev
```

## Extending it

- **New job source**: add a file in `backend/app/connectors/`, subclass
  `BaseConnector`, register it in `registry.py` and the `ConnectorProvider`
  enum in `models.py`. Nothing else needs to change.
- **New follow-up template**: add an entry to `TEMPLATES` in
  `backend/app/services/followup_templates.py`.
- **Resume/JD fit scoring with AI**: `Application.fit_score` and
  `Application.resume_version` fields are already there — the natural next
  step is a `/applications/{id}/score` endpoint that calls an LLM API with the
  job description and your resume text.
