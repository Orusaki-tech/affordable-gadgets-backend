"""Bulk-create Product templates from a supplier price-list CSV.

Designed for the format produced by
``scripts/adhoc/build_supplier_price_list_csv.py`` (i.e.
``inventory/data/supplier_price_list_2026_05_04.csv``).

The command is idempotent — products already present (matched by
``product_name`` or by the model's unique ``(brand, model_series, product_type)``
key) are skipped for creation. The ``ref_sell_kes`` column is used to populate
``Product.default_selling_price`` on both creation and (by default) on re-runs
for existing matched rows; pass ``--no-update-prices`` to disable that backfill,
or ``--overwrite-existing-prices`` to force-overwrite a price that is already
set. ``ref_cost_kes`` is currently unused by this command and is retained in
the CSV as supplier metadata for a follow-up ``InventoryUnit`` importer.

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
from decimal import Decimal, InvalidOperation
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


def _parse_decimal(value: Any) -> Decimal | None:
    """Parse a price-like string (e.g. ``"85,500"`` or ``"85500.50"``) into ``Decimal``.

    Returns ``None`` for blank / unparsable values so callers can skip them.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Allow numbers like "85,500" or "85,500.00" by stripping thousands separators.
    s = s.replace(",", "")
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
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
        "Idempotent: skips products that already exist. "
        "Also reads ``ref_sell_kes`` and populates ``Product.default_selling_price`` — "
        "set on creation, and backfilled on re-runs for existing matched rows (unless "
        "--no-update-prices is passed)."
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
        parser.add_argument(
            "--no-update-prices",
            action="store_true",
            help=(
                "Skip updating Product.default_selling_price on matched existing products. "
                "By default, re-running this command backfills/refreshes default_selling_price "
                "from the CSV's ref_sell_kes column."
            ),
        )
        parser.add_argument(
            "--overwrite-existing-prices",
            action="store_true",
            help=(
                "Overwrite Product.default_selling_price even when it is already set. "
                "By default, existing non-null prices are preserved."
            ),
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"]).expanduser()
        if not csv_path.is_file():
            raise CommandError(f"CSV not found: {csv_path}")

        dry_run = bool(options["dry_run"])
        stop_on_error = bool(options["stop_on_error"])
        update_prices = not bool(options["no_update_prices"])
        overwrite_existing_prices = bool(options["overwrite_existing_prices"])

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

        existing_by_name = {
            p.product_name: p
            for p in Product.objects.only(
                "id", "product_name", "brand", "model_series", "product_type", "default_selling_price"
            )
        }
        existing_by_key = {
            (p.brand, p.model_series, p.product_type): p for p in existing_by_name.values()
        }

        created = 0
        skipped_existing = 0
        skipped_invalid = 0
        failed = 0
        price_updated = 0
        price_skipped_set = 0
        price_skipped_missing = 0
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
                csv_price = _parse_decimal(row.get("ref_sell_kes"))

                existing_product = existing_by_name.get(name) or existing_by_key.get(
                    (brand, model_series, ptype)
                )
                if existing_product is not None:
                    skipped_existing += 1
                    if update_prices:
                        if csv_price is None:
                            price_skipped_missing += 1
                        elif (
                            existing_product.default_selling_price is not None
                            and not overwrite_existing_prices
                        ):
                            price_skipped_set += 1
                        else:
                            if dry_run:
                                self.stdout.write(
                                    f"DRY: would set default_selling_price={csv_price} "
                                    f"on existing [{ptype}] {name!r}"
                                )
                                price_updated += 1
                            else:
                                try:
                                    Product.objects.filter(pk=existing_product.pk).update(
                                        default_selling_price=csv_price
                                    )
                                    price_updated += 1
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f"PRC [{ptype}] {name}: default_selling_price -> {csv_price}"
                                        )
                                    )
                                except Exception as exc:  # noqa: BLE001
                                    failed += 1
                                    errors.append(
                                        f"Row {idx} ({name}): price update failed: {exc}"
                                    )
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f"FAIL price [{ptype}] {name}: {exc}"
                                        )
                                    )
                                    if stop_on_error:
                                        raise
                    continue

                payload = {
                    "product_type": ptype,
                    "product_name": name,
                    "product_description": (row.get("product_description") or "").strip(),
                    "brand": brand,
                    "model_series": model_series,
                    "min_stock_threshold": _parse_int(row.get("min_stock_threshold")),
                    "reorder_point": _parse_int(row.get("reorder_point")),
                    "default_selling_price": csv_price,
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
                    price_note = (
                        f" @ KES {csv_price}" if csv_price is not None else " (no price)"
                    )
                    self.stdout.write(
                        f"DRY: would create {ptype} {name!r} (brand={brand}){price_note}"
                    )
                    created += 1
                    existing_by_name[name] = Product(
                        product_name=name,
                        brand=brand,
                        model_series=model_series,
                        product_type=ptype,
                        default_selling_price=csv_price,
                    )
                    existing_by_key[(brand, model_series, ptype)] = existing_by_name[name]
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
                    existing_by_name[name] = product
                    existing_by_key[(brand, model_series, ptype)] = product
                    price_note = (
                        f" (default_selling_price={csv_price})" if csv_price is not None else ""
                    )
                    self.stdout.write(self.style.SUCCESS(f"OK  [{ptype}] {name}{price_note}"))
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
        if update_prices:
            self.stdout.write(
                self.style.SUCCESS(f"Prices updated:  {price_updated}")
            )
            if price_skipped_set:
                self.stdout.write(
                    f"Prices preserved (already set, pass --overwrite-existing-prices to force): {price_skipped_set}"
                )
            if price_skipped_missing:
                self.stdout.write(
                    f"Prices missing in CSV (existing rows): {price_skipped_missing}"
                )
        else:
            self.stdout.write("Price updates: disabled (--no-update-prices)")
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
