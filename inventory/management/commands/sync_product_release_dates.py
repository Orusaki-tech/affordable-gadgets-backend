from django.core.management.base import BaseCommand

from inventory.models import Product
from inventory.release_date_inference import infer_release_date, match_family_key
from inventory.release_date_table import sync_release_date_table


class Command(BaseCommand):
    help = (
        "Import release month/year into ProductReleaseDate from JSON, "
        "then sync Product.release_date for all matched catalog items."
    )
    def add_arguments(self, parser):
        parser.add_argument(
            "--import-only",
            action="store_true",
            help="Only refresh the ProductReleaseDate table; do not update products.",
        )
        parser.add_argument(
            "--apply-only",
            action="store_true",
            help="Only sync Product.release_date from the existing table.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview changes without writing to the database.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite products that already have release_date set.",
        )
        parser.add_argument(
            "--list-unmatched",
            action="store_true",
            help="Print products that still have no release_date after inference.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]
        list_unmatched = options["list_unmatched"]
        import_only = options["import_only"]
        apply_only = options["apply_only"]

        if not apply_only:
            if dry_run:
                from inventory.release_date_table import iter_release_date_rows

                count = sum(1 for _ in iter_release_date_rows())
                self.stdout.write(f"[dry-run] Would upsert {count} ProductReleaseDate rows")
            else:
                created, updated = sync_release_date_table()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"ProductReleaseDate table: created={created} updated={updated}"
                    )
                )

        if import_only:
            return

        matched = 0
        skipped_existing = 0
        unmatched = 0
        unmatched_names = []

        for product in Product.objects.order_by("id").iterator():
            if product.release_date and not force:
                skipped_existing += 1
                continue

            inferred = infer_release_date(product.product_name)
            if inferred is None:
                unmatched += 1
                if list_unmatched or dry_run:
                    unmatched_names.append(product.product_name)
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
                f"Products synced. matched={matched} skipped_existing={skipped_existing} "
                f"unmatched={unmatched} dry_run={dry_run}"
            )
        )
        if unmatched_names:
            self.stdout.write("Unmatched products:")
            for name in unmatched_names:
                self.stdout.write(f"  - {name}")
