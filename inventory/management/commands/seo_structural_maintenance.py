"""Run all structural SEO maintenance steps (issues 4–9).

Usage::

    python manage.py seo_structural_maintenance --dry-run
    python manage.py seo_structural_maintenance
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

from inventory.management.commands.backfill_slug_redirects import _parse_slug_pairs
from inventory.seo_structural import (
    consolidate_duplicate_products,
    deduplicate_product_articles,
    fix_apostrophe_article_slugs,
    reparent_product_articles,
)

DEFAULT_SLUG_PAIRS_CSV = Path(__file__).resolve().parents[3] / "data" / "seo_duplicate_slug_pairs.csv"

ISSUE_COVERAGE = [
    ("4", "Duplicate product URLs → consolidate + slug redirects"),
    ("5", "Misassigned blog parents → reparent from fixtures + slug token detection"),
    ("6", "Cross-product duplicate articles → deduplicate"),
    ("7", "Apostrophe article slug bugs → fix + article redirects"),
    ("8", "Test products in sitemap → unpublish test products"),
    ("9", "Sitemap lastmod → product/article updated_at (frontend deploy)"),
]


def _load_slug_pairs_csv(path: Path) -> list[tuple[str, str]]:
    if not path.is_file():
        return []
    pairs: list[tuple[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            duplicate = (row.get("duplicate_slug") or row.get("old_slug") or "").strip()
            canonical = (row.get("canonical_slug") or row.get("new_slug") or "").strip()
            if duplicate and canonical:
                pairs.append((duplicate, canonical))
    return pairs


class Command(BaseCommand):
    help = "Run duplicate URL consolidation, article reparenting, deduplication, apostrophe fixes, and test cleanup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview all steps without writing.",
        )
        parser.add_argument(
            "--slug",
            action="append",
            dest="slug_pairs",
            metavar="DUPLICATE=CANONICAL",
            help="Explicit product slug pair for consolidation (repeatable).",
        )
        parser.add_argument(
            "--slug-pairs-csv",
            default=str(DEFAULT_SLUG_PAIRS_CSV),
            help="CSV of duplicate_slug,canonical_slug rows (default: data/seo_duplicate_slug_pairs.csv).",
        )
        parser.add_argument(
            "--skip-test-cleanup",
            action="store_true",
            help="Skip unpublish_test_products step.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        explicit_pairs = _parse_slug_pairs(options.get("slug_pairs"))
        csv_pairs = _load_slug_pairs_csv(Path(options["slug_pairs_csv"]))
        all_pairs = csv_pairs + [
            pair for pair in explicit_pairs if pair not in csv_pairs
        ]

        self.stdout.write(self.style.HTTP_INFO("SEO structural maintenance — issue coverage:"))
        for issue, description in ISSUE_COVERAGE:
            self.stdout.write(f"  [{issue}] {description}")
        if all_pairs:
            self.stdout.write(f"\nExplicit slug pairs loaded: {len(all_pairs)}")

        steps = [
            ("Consolidate duplicate product URLs", lambda: consolidate_duplicate_products(
                dry_run=dry_run,
                explicit_pairs=all_pairs,
            )),
            ("Reparent misassigned articles (from blog fixtures)", None),
            ("Reparent misassigned articles (slug token detection)", lambda: reparent_product_articles(
                dry_run=dry_run,
                auto_detect=True,
            )),
            ("Deduplicate cross-product articles", lambda: deduplicate_product_articles(
                dry_run=dry_run,
            )),
            ("Fix apostrophe article slugs", lambda: fix_apostrophe_article_slugs(
                dry_run=dry_run,
            )),
        ]

        for title, runner in steps:
            self.stdout.write(self.style.HTTP_INFO(f"\n=== {title} ==="))
            if runner is None:
                call_command(
                    "reparent_articles_from_fixtures",
                    dry_run=dry_run,
                    verbosity=1,
                )
                continue
            stats = runner()
            for field in ("scanned", "created", "updated", "deleted", "skipped"):
                value = getattr(stats, field, 0)
                if value:
                    self.stdout.write(f"  {field}: {value}")
            for note in stats.notes[:15]:
                self.stdout.write(f"  {note}")
            if len(stats.notes) > 15:
                self.stdout.write(f"  ... and {len(stats.notes) - 15} more")

        self.stdout.write(self.style.HTTP_INFO("\n=== Backfill product slug redirects ==="))
        call_command(
            "backfill_slug_redirects",
            dry_run=dry_run,
            verbosity=1,
        )

        if not options["skip_test_cleanup"]:
            self.stdout.write(self.style.HTTP_INFO("\n=== Unpublish test products ==="))
            call_command(
                "unpublish_test_products",
                dry_run=dry_run,
                verbosity=1,
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run only — no database changes made."))
        else:
            self.stdout.write(self.style.SUCCESS("\nStructural SEO maintenance complete."))
            self.stdout.write(
                "Deploy frontend to pick up sitemap lastmod (issue 9) and article slug 301 redirects."
            )
