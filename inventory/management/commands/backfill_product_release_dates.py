from django.core.management.base import BaseCommand

from inventory.models import Product
from inventory.release_date_inference import infer_release_date, match_family_key


class Command(BaseCommand):
    help = "Backfill nullable Product.release_date from curated family lookup."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview matches without writing to the database.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite products that already have release_date set.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        matched = 0
        skipped_existing = 0
        unmatched = 0

        for product in Product.objects.order_by("id").iterator():
            if product.release_date and not force:
                skipped_existing += 1
                continue

            inferred = infer_release_date(product.product_name)
            if inferred is None:
                unmatched += 1
                continue

            family_key = match_family_key(product.product_name)
            if dry_run:
                self.stdout.write(
                    f"[dry-run] {product.id} {product.product_name!r} -> "
                    f"{family_key} = {inferred.isoformat()}"
                )
            else:
                product.release_date = inferred
                product.save(update_fields=["release_date", "updated_at"])

            matched += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. matched={matched} skipped_existing={skipped_existing} "
                f"unmatched={unmatched} dry_run={dry_run}"
            )
        )
