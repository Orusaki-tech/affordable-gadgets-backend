# Affordable Gadgets Backend

Django REST API backend for the Affordable Gadgets e-commerce platform (inventory, orders, and storefront API).

**Running locally?** See [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) for setup (`.env` + `.env.local`).

## Features

- **Inventory** – Products, units, categories, brands, promotions, images (Cloudinary)
- **Orders & sales** – Cart, checkout, M-Pesa and Pesapal payments, receipts
- **Admin API** – Token auth, CRUD, reports; optional [Django Silk](https://github.com/jazzband/django-silk) profiling at `/silk/`
- **Public API** – Read-only product catalog and endpoints for the e-commerce frontend
- **API docs** – OpenAPI 3 (Swagger UI at `/api/schema/swagger-ui/`, ReDoc at `/api/schema/redoc/`)

## Quick start

1. Copy env: `cp .env.example .env` and `cp .env.local.example .env.local`
2. `python manage.py migrate`
3. `python manage.py runserver` → http://127.0.0.1:8000

## Docs

| Doc | Description |
|-----|-------------|
| [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) | Local setup, env files, database |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Deploy (e.g. Render, Railway) |
| [PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) | Pre-launch checklist |
| [scripts/README_IMPORT.md](scripts/README_IMPORT.md) | Import inventory via API |
| [docs/](docs/) | Other guides (Railway keep-warm, etc.) |

## Lint / format

```bash
ruff check .
ruff format .
```(Ruff config in `pyproject.toml`.)
