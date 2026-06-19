"""Load and sync ProductReleaseDate rows from curated JSON files."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _family_label(family_key: str) -> str:
    return family_key.replace("-", " ").title()


def load_release_date_json() -> dict[str, date]:
    path = _DATA_DIR / "product-release-dates.json"
    with path.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    exact_path = _DATA_DIR / "product-release-dates-exact.json"
    if exact_path.exists():
        with exact_path.open(encoding="utf-8") as handle:
            raw.update(json.load(handle))
    return {key: date.fromisoformat(value) for key, value in raw.items()}


def load_release_date_sources() -> dict[str, dict]:
    path = _DATA_DIR / "product-release-date-sources.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def iter_release_date_rows():
    """Yield dicts ready for ProductReleaseDate upsert."""
    dates = load_release_date_json()
    sources = load_release_date_sources()

    for family_key, release_date in dates.items():
        meta = sources.get(family_key, {})
        if "release_month" in meta and "release_year" in meta:
            month = int(meta["release_month"])
            year = int(meta["release_year"])
        else:
            month = release_date.month
            year = release_date.year

        yield {
            "family_key": family_key,
            "product_label": meta.get("product_label") or _family_label(family_key),
            "release_month": month,
            "release_year": year,
            "source_url": meta.get("source_url", ""),
            "notes": meta.get("notes", ""),
        }


def sync_release_date_table(*, dry_run: bool = False) -> tuple[int, int]:
    """Upsert ProductReleaseDate rows from JSON. Returns (created, updated)."""
    from inventory.models import ProductReleaseDate

    created = 0
    updated = 0

    for row in iter_release_date_rows():
        if dry_run:
            continue

        _, was_created = ProductReleaseDate.objects.update_or_create(
            family_key=row["family_key"],
            defaults={
                "product_label": row["product_label"],
                "release_month": row["release_month"],
                "release_year": row["release_year"],
                "source_url": row["source_url"],
                "notes": row["notes"],
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    if not dry_run:
        from inventory.release_date_inference import clear_release_date_lookup_cache

        clear_release_date_lookup_cache()

    return created, updated
