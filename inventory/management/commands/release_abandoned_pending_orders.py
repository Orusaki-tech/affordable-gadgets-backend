"""Cancel abandoned unpaid pending orders and free unique inventory units."""

from django.core.management.base import BaseCommand

from inventory.services.order_release_service import OrderReleaseService


class Command(BaseCommand):
    help = (
        "Release unpaid PENDING orders older than N hours (default: 2). "
        "Restores unique units from PENDING_PAYMENT/RESERVED to AVAILABLE "
        "(online) or RESERVED (walk-in). Never touches orders with items paid "
        "or a COMPLETED Pesapal payment."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=float,
            default=2.0,
            help="Release orders older than this many hours (default: 2)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count candidates without canceling orders",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=500,
            help="Max orders to process per run (default: 500)",
        )

    def handle(self, *args, **options):
        result = OrderReleaseService.release_abandoned_pending_orders(
            older_than_hours=max(options["hours"], 0.1),
            dry_run=options["dry_run"],
            limit=max(options["limit"], 1),
        )
        verb = "Would release" if result["dry_run"] else "Released"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {result['released']}/{result['candidates']} abandoned "
                f"pending order(s) older than {result['older_than_hours']}h."
            )
        )
