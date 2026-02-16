# Local PostgreSQL with Docker

Use this for a local database for development and testing (e.g. `audit_query_counts`, tests).

## Start Postgres

```bash
docker compose up -d
```

Wait a few seconds for the DB to be ready, then:

## Point Django at it

In your `.env`:

```bash
DATABASE_URL=postgresql://affordable:affordable@localhost:5432/affordable_gadgets
```

(Leave `DATABASE_URL` unset to use SQLite instead.)

## Migrate and run

```bash
python manage.py migrate
python manage.py runserver
# or
python manage.py audit_query_counts
```

## Useful commands

- **Stop:** `docker compose down`
- **Stop and remove data:** `docker compose down -v`
- **Logs:** `docker compose logs -f postgres`

Credentials (local only): user `affordable`, password `affordable`, database `affordable_gadgets`.
