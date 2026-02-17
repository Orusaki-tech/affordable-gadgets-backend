# Keeping the Railway backend warm

## Why this is needed

On Railway (and similar platforms), the backend can go idle after a period of no traffic. The **first request after idle** (cold start) can take **30–60+ seconds** or time out. That affects:

- Admin login (POST to `/api/auth/token/login/`)
- Any first API call from the frontend after idle

The slowness is from **infrastructure cold start**, not from the application code. Keeping the backend warm avoids long waits and timeouts for users.

## Option 1: GitHub Actions (in-repo, recommended)

This repo includes a workflow that pings the production backend every 5 minutes.

- **Workflow**: [.github/workflows/keep-warm.yml](../.github/workflows/keep-warm.yml)
- **Schedule**: `*/5 * * * *` (every 5 minutes)
- **URL pinged**: `https://web-production-ffde2.up.railway.app/health/` (or `/` if `/health/` fails)

**Setup:**

1. Push the workflow to your default branch so it runs on schedule.
2. If your production URL is different, set a repository variable:
   - Repo → **Settings** → **Secrets and variables** → **Actions** → **Variables**
   - Add `BACKEND_URL` = `https://your-railway-app.up.railway.app`

**Manual run:** Actions → **Keep backend warm** → **Run workflow**.

## Option 2: External uptime monitor

Use a free service to hit your backend on an interval.

**UptimeRobot**

1. Sign up at [uptimerobot.com](https://uptimerobot.com).
2. Add a monitor:
   - Type: HTTP(s)
   - URL: `https://your-backend.railway.app/health/` (or `/`)
   - Interval: 5 minutes

**cron-job.org**

1. Sign up at [cron-job.org](https://cron-job.org).
2. Create a cron job:
   - URL: `https://your-backend.railway.app/health/`
   - Schedule: every 5 minutes

## Health endpoint

The backend exposes a lightweight endpoint for pings:

- **URL**: `GET /health/`
- **Response**: `{"status": "ok"}` (no DB or auth)

Use `/health/` for keep-warm so the root `/` endpoint is not required for monitoring.
