"""Import BuySimu (409) financing offers from CSV onto Product rows.

Matches Excel models to existing Product records by normalized name, then
upserts FinancingOffer rows for 12-week / 16-week / 24-week terms under the
Buy Simu provider.

Usage::

    python manage.py import_buysimu_financing --dry-run
    python manage.py import_buysimu_financing --publish
"""

from __future__ import annotations

import csv
import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from inventory.models import FinancingOffer, FinancingProvider, Product

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
DEFAULT_CSV = DATA_DIR / "buysimu_409_financing.csv"

PROVIDER_NAME = "Buy Simu"
PROVIDER_SLUG = "buy-simu"


def _norm_model(name: str) -> str:
    s = re.sub(r"\s+", " ", (name or "").strip())
    s = re.sub(r"\bMini\b", "mini", s, flags=re.I)
    return s.casefold()


def _parse_int(value) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(round(float(s)))
    except ValueError:
        return None


def _parse_decimal(value) -> Decimal | None:
    n = _parse_int(value)
    if n is None:
        return None
    return Decimal(n)


def _rom_from_specs(specs: str, rom_gb: int | None) -> int | None:
    if rom_gb is not None:
        # Combo rows like "1TB &512GB" — prefer explicit GB when both present.
        if "TB" in specs.upper() and "GB" in specs.upper():
            m = re.search(r"(\d+)\s*GB", specs, re.I)
            if m:
                return int(m.group(1))
        return rom_gb
    m = re.search(r"(\d+)\s*GB", specs or "", re.I)
    return int(m.group(1)) if m else None


class Command(BaseCommand):
    help = "Import BuySimu 409 financing offers onto matching products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default=str(DEFAULT_CSV),
            help="Path to buysimu_409_financing.csv",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and match only; do not write.",
        )
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Set is_published=True on products that receive offers.",
        )
        parser.add_argument(
            "--provider-slug",
            type=str,
            default=PROVIDER_SLUG,
            help="Financing provider slug (default: buy-simu).",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv"])
        if not csv_path.is_file():
            raise CommandError(f"CSV not found: {csv_path}")

        dry_run = bool(options["dry_run"])
        publish = bool(options["publish"])
        provider_slug = options["provider_slug"]

        provider, _ = FinancingProvider.objects.get_or_create(
            slug=provider_slug,
            defaults={"name": PROVIDER_NAME, "is_active": True},
        )
        if not provider.is_active:
            provider.is_active = True
            if not dry_run:
                provider.save(update_fields=["is_active", "updated_at"])

        products = list(
            Product.objects.filter(product_name__icontains="iPhone").exclude(
                Q(product_name__icontains="charger")
                | Q(product_name__icontains="earphone")
                | Q(product_name__icontains="cover")
                | Q(product_name__icontains="Pocket")
            )
        )
        by_norm: dict[str, list[Product]] = {}
        for p in products:
            by_norm.setdefault(_norm_model(p.product_name), []).append(p)

        created = updated = skipped = unmatched = published = 0
        unmatched_models: list[str] = []

        with csv_path.open(newline="") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)

        with transaction.atomic():
            for row in rows:
                model = (row.get("model") or "").strip()
                specs = (row.get("specs") or "").strip()
                if not model:
                    continue

                rom = _rom_from_specs(specs, _parse_int(row.get("rom_gb")))
                cash = _parse_decimal(row.get("cash_price"))
                if cash is None:
                    skipped += 1
                    continue

                product = self._resolve_product(model, by_norm)
                if product is None:
                    unmatched += 1
                    unmatched_models.append(f"{model} ({specs})")
                    self.stdout.write(self.style.WARNING(f"No product match: {model} {specs}"))
                    continue

                term_specs = [
                    (12, row.get("deposit_12"), row.get("weekly_12")),
                    (16, row.get("deposit_12"), row.get("weekly_16")),
                    (24, row.get("deposit_24"), row.get("weekly_24")),
                ]
                touched = False
                for term_count, deposit_raw, weekly_raw in term_specs:
                    deposit = _parse_decimal(deposit_raw)
                    weekly = _parse_decimal(weekly_raw)
                    if deposit is None or weekly is None:
                        continue
                    if deposit > cash:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Skip {model} {specs} {term_count}w: deposit > cash"
                            )
                        )
                        continue

                    defaults = {
                        "deposit_amount": deposit,
                        "retail_amount": cash,
                        "weekly_payment": weekly,
                        "daily_payment": None,
                        "monthly_payment": None,
                        "is_active": True,
                    }
                    if dry_run:
                        exists = FinancingOffer.objects.filter(
                            provider=provider,
                            product=product,
                            rom_gb=rom,
                            ram_gb=None,
                        ).filter(
                            Q(term_count=term_count, term_unit=FinancingOffer.TermUnit.WEEK)
                            | Q(term_count__isnull=True, term_unit__isnull=True)
                        ).exists()
                        if exists:
                            updated += 1
                        else:
                            created += 1
                        touched = True
                        continue

                    obj, was_created = self._upsert_offer(
                        provider=provider,
                        product=product,
                        rom_gb=rom,
                        term_count=term_count,
                        defaults=defaults,
                    )
                    touched = True
                    if was_created:
                        created += 1
                        self.stdout.write(
                            f"Created {product.product_name} {rom}GB {term_count}w "
                            f"dep={deposit} weekly={weekly}"
                        )
                    else:
                        updated += 1
                        self.stdout.write(
                            f"Updated {product.product_name} {rom}GB {term_count}w "
                            f"dep={deposit} weekly={weekly} (id={obj.id})"
                        )

                if touched and publish and (not product.is_published or product.is_discontinued):
                    if not dry_run:
                        product.is_published = True
                        product.is_discontinued = False
                        product.save(update_fields=["is_published", "is_discontinued", "updated_at"])
                    published += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Published {product.product_name} (id={product.id})")
                    )

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created} updated={updated} skipped={skipped} "
                f"unmatched={unmatched} published={published} dry_run={dry_run}"
            )
        )
        if unmatched_models:
            self.stdout.write("Unmatched:")
            for m in unmatched_models:
                self.stdout.write(f"  - {m}")

    def _upsert_offer(
        self,
        *,
        provider: FinancingProvider,
        product: Product,
        rom_gb: int | None,
        term_count: int,
        defaults: dict,
    ) -> tuple[FinancingOffer, bool]:
        """Update exact term row, or migrate a legacy null-term offer into it."""
        exact = FinancingOffer.objects.filter(
            provider=provider,
            product=product,
            ram_gb=None,
            rom_gb=rom_gb,
            term_unit=FinancingOffer.TermUnit.WEEK,
            term_count=term_count,
        ).first()
        if exact:
            for key, value in defaults.items():
                setattr(exact, key, value)
            exact.term_unit = FinancingOffer.TermUnit.WEEK
            exact.term_count = term_count
            exact.is_active = True
            exact.save()
            return exact, False

        legacy = None
        if term_count == 12:
            legacy = (
                FinancingOffer.objects.filter(
                    provider=provider,
                    product=product,
                    ram_gb=None,
                    rom_gb=rom_gb,
                    term_unit__isnull=True,
                    term_count__isnull=True,
                )
                .order_by("id")
                .first()
            )
        if legacy:
            for key, value in defaults.items():
                setattr(legacy, key, value)
            legacy.term_unit = FinancingOffer.TermUnit.WEEK
            legacy.term_count = term_count
            legacy.is_active = True
            legacy.save()
            return legacy, False

        obj = FinancingOffer.objects.create(
            provider=provider,
            product=product,
            ram_gb=None,
            rom_gb=rom_gb,
            term_unit=FinancingOffer.TermUnit.WEEK,
            term_count=term_count,
            deposit_amount=defaults["deposit_amount"],
            retail_amount=defaults["retail_amount"],
            weekly_payment=defaults["weekly_payment"],
            daily_payment=defaults.get("daily_payment"),
            monthly_payment=defaults.get("monthly_payment"),
            is_active=True,
        )
        return obj, True

    def _resolve_product(self, model: str, by_norm: dict[str, list[Product]]) -> Product | None:
        key = _norm_model(model)
        candidates = by_norm.get(key) or []

        # Soft aliases for renamed catalog rows
        aliases = {
            _norm_model("iPhone 16 Pro Max"): [
                _norm_model("iPhone 16 Pro Max Desert"),
                _norm_model("iPhone 16 Pro Max SIM Desert"),
                _norm_model("iPhone 16 Pro Max SIM Active"),
            ],
            _norm_model("iPhone 13 mini"): [_norm_model("iPhone 13 Mini")],
            _norm_model("iPhone 12 mini"): [_norm_model("iPhone 12 Mini")],
        }
        for alias in aliases.get(key, []):
            candidates = candidates or by_norm.get(alias) or []

        if not candidates:
            # Starts-with match excluding SIM/E-SIM color SKUs when possible
            for norm, group in by_norm.items():
                if norm.startswith(key) or key.startswith(norm):
                    candidates.extend(group)

        if not candidates:
            return None

        # Prefer exact name (case-insensitive), then published, then fewest extra suffixes
        def score(p: Product) -> tuple:
            exact = 0 if _norm_model(p.product_name) == key else 1
            pub = 0 if p.is_published else 1
            simmy = 1 if re.search(r"\b(SIM|E-SIM|Desert|Glacier)\b", p.product_name, re.I) else 0
            return (exact, pub, simmy, len(p.product_name), p.id)

        return sorted(candidates, key=score)[0]
