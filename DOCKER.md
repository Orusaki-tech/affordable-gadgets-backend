# Docker: Backend + PostgreSQL

Two ways to use Docker:

1. **Full stack (web + postgres)** – run the Django app and DB in containers (local or GCP).
2. **Postgres only** – run only the DB in Docker; run Django on the host (see “Postgres only” below).

---

## Full stack (web + postgres)

Build and run the backend and Postgres:

```bash
docker compose up -d --build
```

The **web** service runs `startup.sh`: migrate (with retries) → collectstatic → Gunicorn on port 8000.

### Required .env for the web container

Ensure `.env` exists and includes at least:

- `SECRET_KEY` – e.g. from `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
- `ALLOWED_HOSTS` – e.g. `localhost,127.0.0.1` for local; add your GCP VM IP or domain for production

Optional but recommended: `CORS_ALLOWED_ORIGINS`, `FRONTEND_BASE_URL`, Cloudinary and Pesapal vars.

`DATABASE_URL` is set by docker-compose to `postgresql://affordable:affordable@postgres:5432/affordable_gadgets` so the app talks to the postgres service.

### Useful commands

- **Logs:** `docker compose logs -f web`
- **Stop:** `docker compose down`
- **Stop and remove data:** `docker compose down -v`
- **Rebuild after code change:** `docker compose up -d --build`

App: http://localhost:8000

---

## Postgres only (Django on host)

If you only want Postgres in Docker and Django on your machine:

1. Start postgres: `docker compose up -d postgres`
2. In `.env`: `DATABASE_URL=postgresql://affordable:affordable@localhost:5432/affordable_gadgets`
3. Run Django on the host: `python manage.py migrate && python manage.py runserver`

Credentials (local): user `affordable`, password `affordable`, database `affordable_gadgets`.

---

## Using this image on GCP

- Build the image (locally or in CI): `docker build -t affordable-gadgets-backend .`
- Push to a registry (Artifact Registry, Docker Hub, etc.) or copy the Dockerfile + context to the GCP VM and build there.
- On the VM: run the same image with Postgres (e.g. `docker compose` with your production `.env` and `DATABASE_URL` pointing at the DB). Terraform can create the VM; you install Docker and run compose or `docker run` with the same env.
