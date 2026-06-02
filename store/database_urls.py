"""Parse PostgreSQL DATABASE_URL values for Django DATABASES entries."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlparse


def database_config_from_url(url: str, *, conn_max_age: int | None = None) -> dict:
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    options: dict = {"connect_timeout": 10}
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        options[key] = value
    if "sslmode" not in options and host not in ("localhost", "127.0.0.1"):
        options["sslmode"] = "require"
    if host in ("localhost", "127.0.0.1") and "sslmode" not in options:
        options["sslmode"] = "disable"

    cfg = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/").split("?")[0],
        "USER": parsed.username,
        "PASSWORD": parsed.password,
        "HOST": parsed.hostname,
        "PORT": parsed.port or "5432",
        "OPTIONS": options,
    }
    if conn_max_age is not None:
        cfg["CONN_MAX_AGE"] = conn_max_age
    return cfg
