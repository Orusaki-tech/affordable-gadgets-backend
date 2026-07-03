"""Audit blog articles filed under the wrong product URL.

Uses slug token overlap between article slug and parent product slug to flag
misassignments and suggest the best matching catalog product.

Usage::

    python manage.py audit_article_mismatches
    python manage.py audit_article_mismatches --min-confidence 0.75
    python manage.py audit_article_mismatches --csv data/article_mismatches.csv
    python manage.py audit_article_mismatches --apply
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from inventory.seo_structural import detect_article_mismatches, reparent_product_articles


class Command(BaseCommand):
    help = "Flag blog articles whose slug model doesn't match their parent product slug."

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-confidence",
            type=float,
            default=0.5,
            help="Minimum match confidence (0–1) to include in output (default: 0.5).",
        )
        parser.add_argument(
            "--csv",
            metavar="PATH",
            help="Write mismatches to CSV (article_id,article_slug,current_product,suggested_product,confidence).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Reparent flagged articles (respects slug collision checks).",
        )
        parser.add_argument(
            "--include-unpublished",
            action="store_true",
            help="Include unpublished articles in the audit.",
        )

    def handle(self, *args, **options):
        min_confidence = options["min_confidence"]
        mismatches = detect_article_mismatches(
            min_confidence=min_confidence,
            published_only=not options["include_unpublished"],
        )

        self.stdout.write(f"Mismatches found: {len(mismatches)} (min confidence {min_confidence})")
        for row in mismatches[:60]:
            self.stdout.write(
                f"  id={row.article_id} {row.article_slug}\n"
                f"    {row.current_product_slug} -> {row.suggested_product_slug} "
                f"(confidence={row.confidence:.2f})"
            )
        if len(mismatches) > 60:
            self.stdout.write(f"  ... and {len(mismatches) - 60} more")

        csv_path = (options.get("csv") or "").strip()
        if csv_path:
            self._write_csv(Path(csv_path), mismatches)

        if options["apply"]:
            self.stdout.write(self.style.HTTP_INFO("\nApplying slug-based reparenting..."))
            stats = reparent_product_articles(dry_run=False, auto_detect=True)
            self.stdout.write(f"Reparented: {stats.updated}, skipped: {stats.skipped}")
            for note in stats.notes[:20]:
                self.stdout.write(f"  {note}")
            self.stdout.write(self.style.SUCCESS("Reparenting complete."))

    def _write_csv(self, path: Path, mismatches) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "article_id",
                    "article_slug",
                    "headline",
                    "current_product_slug",
                    "suggested_product_slug",
                    "confidence",
                    "reason",
                ],
            )
            writer.writeheader()
            for row in mismatches:
                writer.writerow(
                    {
                        "article_id": row.article_id,
                        "article_slug": row.article_slug,
                        "headline": row.headline,
                        "current_product_slug": row.current_product_slug,
                        "suggested_product_slug": row.suggested_product_slug,
                        "confidence": f"{row.confidence:.2f}",
                        "reason": row.reason,
                    }
                )
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(mismatches)} rows to {path}"))
