"""
Remove blogs recreated by load_blog_batch after intentional deletes, and tombstone them.

Example (production recreation wave on 2026-07-13):
  python manage.py purge_recreated_articles --since 2026-07-13T02:00:00Z --dry-run
  python manage.py purge_recreated_articles --since 2026-07-13T02:00:00Z
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from inventory.models import ProductArticle, ProductArticleTombstone


class Command(BaseCommand):
    help = "Delete ProductArticles created on/after a timestamp and record tombstones."

    def add_arguments(self, parser):
        parser.add_argument(
            "--since",
            required=True,
            help="ISO datetime (UTC recommended), e.g. 2026-07-13T02:00:00Z",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List matches without deleting.",
        )

    def handle(self, *args, **options):
        raw = options["since"]
        since = parse_datetime(raw)
        if since is None:
            raise CommandError(f"Could not parse --since={raw!r}")
        if timezone.is_naive(since):
            since = timezone.make_aware(since, timezone.utc)

        qs = ProductArticle.objects.filter(created_at__gte=since).select_related("product")
        count = qs.count()
        self.stdout.write(f"Matched {count} article(s) with created_at >= {since.isoformat()}")

        if options["dry_run"]:
            for article in qs.order_by("id")[:30]:
                product_name = article.product.product_name if article.product_id else "(standalone)"
                self.stdout.write(
                    f"  would delete #{article.id} {product_name} · {article.slug}"
                )
            if count > 30:
                self.stdout.write(f"  ... and {count - 30} more")
            return

        deleted = 0
        for article in qs.iterator():
            ProductArticleTombstone.record_from_article(article)
            article.delete()
            deleted += 1

        self.stdout.write(self.style.SUCCESS(f"Deleted and tombstoned {deleted} article(s)."))
