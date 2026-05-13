"""Bulk-create Product templates from a supplier price-list CSV.

Designed for the format produced by
``scripts/adhoc/build_supplier_price_list_csv.py`` (i.e.
``inventory/data/supplier_price_list_2026_05_04.csv``).

The command is idempotent — products already present (matched by
``product_name`` or by the model's unique ``(brand, model_series, product_type)``
key) are skipped. ``ref_cost_kes`` and ``ref_sell_kes`` columns in the CSV are
ignored by this command; they are kept as metadata so a follow-up command can
create ``InventoryUnit`` rows once stock arrives.

Usage:

    # Default: imports inventory/data/supplier_price_list_2026_05_04.csv
    python manage.py import_supplier_price_list

    # Custom CSV and audit user
    python manage.py import_supplier_price_list \\
        --csv inventory/data/supplier_price_list_2026_05_04.csv \\
        --user admin

    # Dry-run (no DB writes, just shows what would happen)
    python manage.py import_supplier_price_list --dry-run
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from inventory.models import Brand, Product, Tag

User = get_user_model()

DEFAULT_CSV = (
    Path(__file__).resolve().parents[3]
    / "inventory"
    / "data"
    / "supplier_price_list_2026_05_04.csv"
)

VALID_PRODUCT_TYPES = {choice[0] for choice in Product.ProductType.choices}


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ("true", "1", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n", ""):
        return False
    return default


def _parse_int(value: Any) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_json_list(value: Any) -> list:
    if value is None:
        return []
    s = str(value).strip()
    if not s:
        return []
    try:
        parsed = json.loads(s)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


class Command(BaseCommand):
    help = (
        "Bulk-create Product templates from a supplier price-list CSV. "
        "Idempotent: skips products that already exist."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=str(DEFAULT_CSV),
            help=f"Path to the CSV file (default: {DEFAULT_CSV})",
        )
        parser.add_argument(
            "--user",
            type=str,
            default="admin",
            help="Username to set as created_by on imported products (default: admin)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without writing to the database",
        )
        parser.add_argument(
            "--stop-on-error",
            action="store_true",
            help="Abort the whole import if any single row fails (default: keep going)",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"]).expanduser()
        if not csv_path.is_file():
            raise CommandError(f"CSV not found: {csv_path}")

        dry_run = bool(options["dry_run"])
        stop_on_error = bool(options["stop_on_error"])

        created_by = None
        try:
            created_by = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            self.stdout.write(
                self.style.WARNING(
                    f"User '{options['user']}' not found — products will be created without created_by."
                )
            )

        self.stdout.write(self.style.HTTP_INFO(f"Reading {csv_path}"))
        with csv_path.open("r", newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))

        self.stdout.write(f"Found {len(rows)} rows in CSV.")
        if dry_run:
            self.stdout.write(self.style.WARNING("Running in --dry-run mode (no DB writes)."))

        existing_names = set(Product.objects.values_list("product_name", flat=True))
        existing_keys = set(
            Product.objects.values_list("brand", "model_series", "product_type")
        )

        created = 0
        skipped_existing = 0
        skipped_invalid = 0
        failed = 0
        errors: list[str] = []

        sid = None
        if not dry_run:
            sid = transaction.savepoint()

        try:
            for idx, row in enumerate(rows, start=2):  # row 2 = first data row after header
                name = (row.get("product_name") or "").strip()
                if not name:
                    skipped_invalid += 1
                    errors.append(f"Row {idx}: missing product_name; skipped.")
                    continue

                ptype = (row.get("product_type") or "").strip().upper()
                if ptype not in VALID_PRODUCT_TYPES:
                    skipped_invalid += 1
                    errors.append(
                        f"Row {idx} ({name}): invalid product_type {ptype!r}; "
                        f"expected one of {sorted(VALID_PRODUCT_TYPES)}."
                    )
                    continue

                brand = (row.get("brand") or "").strip() or "N/A"
                model_series = (row.get("model_series") or "").strip() or "N/A"

                if name in existing_names:
                    skipped_existing += 1
                    continue
                if (brand, model_series, ptype) in existing_keys:
                    skipped_existing += 1
                    continue

                payload = {
                    "product_type": ptype,
                    "product_name": name,
                    "product_description": (row.get("product_description") or "").strip(),
                    "brand": brand,
                    "model_series": model_series,
                    "min_stock_threshold": _parse_int(row.get("min_stock_threshold")),
                    "reorder_point": _parse_int(row.get("reorder_point")),
                    "is_discontinued": _parse_bool(row.get("is_discontinued"), default=False),
                    "meta_title": (row.get("meta_title") or "").strip()[:60],
                    "meta_description": (row.get("meta_description") or "").strip()[:160],
                    "keywords": (row.get("keywords") or "").strip()[:255],
                    "product_highlights": _parse_json_list(row.get("product_highlights")),
                    "long_description": (row.get("long_description") or "").strip(),
                    "is_published": _parse_bool(row.get("is_published"), default=True),
                    "product_video_url": (row.get("product_video_url") or "").strip() or None,
                    "is_global": _parse_bool(row.get("is_global"), default=False),
                }
                # Slug intentionally omitted — Product.save() generates one from
                # brand + model_series + product_name automatically.

                if created_by is not None:
                    payload["created_by"] = created_by
                    payload["updated_by"] = created_by

                if dry_run:
                    self.stdout.write(f"DRY: would create {ptype} {name!r} (brand={brand})")
                    created += 1
                    existing_names.add(name)
                    existing_keys.add((brand, model_series, ptype))
                    continue

                try:
                    with transaction.atomic():
                        product = Product.objects.create(**payload)

                        # Attach brands and tags if specified in CSV
                        brand_ids = _parse_json_list(row.get("brand_ids"))
                        if brand_ids:
                            brands = list(Brand.objects.filter(id__in=brand_ids))
                            if brands:
                                product.brands.set(brands)
                        tag_ids = _parse_json_list(row.get("tag_ids"))
                        if tag_ids:
                            tags = list(Tag.objects.filter(id__in=tag_ids))
                            if tags:
                                product.tags.set(tags)

                    created += 1
                    existing_names.add(name)
                    existing_keys.add((brand, model_series, ptype))
                    self.stdout.write(self.style.SUCCESS(f"OK  [{ptype}] {name}"))
                except Exception as exc:  # noqa: BLE001 - we want to surface any DB/validation error
                    failed += 1
                    errors.append(f"Row {idx} ({name}): {exc}")
                    self.stdout.write(self.style.ERROR(f"FAIL [{ptype}] {name}: {exc}"))
                    if stop_on_error:
                        raise

            if not dry_run and sid is not None:
                transaction.savepoint_commit(sid)
        except Exception:
            if not dry_run and sid is not None:
                transaction.savepoint_rollback(sid)
            raise

        # --- Summary -------------------------------------------------------
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("=== Import summary ==="))
        self.stdout.write(f"CSV file:        {csv_path}")
        self.stdout.write(f"Total rows:      {len(rows)}")
        self.stdout.write(self.style.SUCCESS(f"Created:         {created}"))
        self.stdout.write(f"Skipped (exists): {skipped_existing}")
        self.stdout.write(f"Skipped (invalid): {skipped_invalid}")
        if failed:
            self.stdout.write(self.style.ERROR(f"Failed:          {failed}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("(dry-run — no products were written)"))
        if errors:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"Issues encountered ({len(errors)}):"))
            for line in errors[:50]:
                self.stdout.write(f"  - {line}")
            if len(errors) > 50:
                self.stdout.write(f"  ... and {len(errors) - 50} more.")
