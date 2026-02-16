# Local Development Setup

This project uses **two env files** so you can keep production values in `.env` and override only what’s needed for local runs.

## Why two files?

- **`.env`** – Shared or production values (Render, DB URL, Cloudinary, etc.). You can keep this as-is for production.
- **`.env.local`** – Local-only overrides. Loaded *after* `.env` and overrides those values when the file exists. Gitignored so you never commit local settings.

When `DJANGO_ENV=production`, Django loads `settings_production.py`, which turns on HTTPS redirect, strict CORS, and secure cookies. That breaks **http://localhost:8000**. For local dev we use development mode so HTTP and localhost work.

## Quick start (local)

1. **Create local overrides**
   ```bash
   cp .env.local.example .env.local
   ```
   `.env.local` already sets `DJANGO_ENV=development` and `DEBUG=True`. Edit if you need to (e.g. SQLite, console email).

2. **Database**
   - To use **SQLite** (no Postgres): in `.env.local` set `DATABASE_URL=` (empty) or leave it out.
   - To use **local Postgres**: ensure Postgres is running and `DATABASE_URL` in `.env` (or `.env.local`) points at it, e.g. `postgresql://affordable:affordable@localhost:5432/affordable_gadgets`.

3. **Migrations**
   ```bash
   python manage.py migrate
   ```

4. **Run the server**
   ```bash
   python manage.py runserver
   ```
   Open **http://localhost:8000**. No HTTPS redirect; CORS allows your local frontend (e.g. http://localhost:3000).

## What `.env.local` overrides

| Variable | Effect |
|----------|--------|
| `DJANGO_ENV=development` | Skips production settings (no HTTPS redirect, no strict CORS). |
| `DEBUG=True` | Enables Django debug page and localhost in `ALLOWED_HOSTS`. |
| `DATABASE_URL=` | Use SQLite (`db.sqlite3`) when empty. |
| `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` | Print emails to the terminal instead of sending. |

## Production (Render)

On Render, do **not** create `.env.local`. Set env vars in the Render dashboard (or use the same values as in `.env`). Use `DJANGO_ENV=production`, `DEBUG=False`, and your production `DATABASE_URL` and CORS origins.
