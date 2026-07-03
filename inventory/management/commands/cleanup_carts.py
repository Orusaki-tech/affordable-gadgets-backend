"""Management command to clean up expired and stale carts."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from inventory.models import Cart, Lead


class Command(BaseCommand):
    help = (
        "Clean up expired carts, stale unsubmitted carts (default: older than 2 months), "
        "and carts for closed/expired leads (after 7 day grace period)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--stale-months",
            type=int,
            default=2,
            help="Delete unsubmitted carts not updated in this many months (default: 2)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many carts would be deleted without deleting",
        )
        parser.add_argument(
            "--purge-anonymous",
            action="store_true",
            help="Delete all unsubmitted carts with no linked customer (legacy session carts)",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        grace_period = timedelta(days=7)
        stale_months = max(options["stale_months"], 0)
        stale_cutoff = now - timedelta(days=stale_months * 30)
        dry_run = options["dry_run"]

        # 1. Clean up unsubmitted expired carts (24h TTL)
        expired_carts = Cart.objects.filter(is_submitted=False, expires_at__lt=now)
        expired_count = expired_carts.count()
        if not dry_run:
            expired_carts.delete()

        # 2. Clean up stale unsubmitted carts (legacy anonymous/session carts accumulate here)
        stale_carts = Cart.objects.filter(
            is_submitted=False,
            updated_at__lt=stale_cutoff,
        )
        stale_count = stale_carts.count()
        stale_anonymous_count = stale_carts.filter(customer__isnull=True).count()
        stale_linked_count = stale_carts.filter(customer__user__isnull=False).count()
        if not dry_run:
            stale_carts.delete()

        # 3. Purge legacy anonymous carts (no customer linked)
        anonymous_carts = Cart.objects.filter(is_submitted=False, customer__isnull=True)
        anonymous_count = anonymous_carts.count()
        if options["purge_anonymous"] and not dry_run:
            anonymous_carts.delete()
        elif options["purge_anonymous"]:
            pass  # counted for reporting only
        else:
            anonymous_count = 0

        # 4. Clean up carts for closed/expired leads (after 7 day grace period)
        closed_expired_leads = Lead.objects.filter(
            status__in=[Lead.StatusChoices.CLOSED, Lead.StatusChoices.EXPIRED],
            submitted_at__lt=now - grace_period,
        )

        closed_carts_count = 0
        if not dry_run:
            for lead in closed_expired_leads:
                try:
                    cart = Cart.objects.filter(lead=lead).first()
                    if cart:
                        cart.delete()
                        closed_carts_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Could not delete cart for lead {lead.lead_reference}: {str(e)}"
                        )
                    )
        else:
            closed_carts_count = sum(
                1 for lead in closed_expired_leads if Cart.objects.filter(lead=lead).exists()
            )

        total_count = expired_count + stale_count + anonymous_count + closed_carts_count
        mode = "Would delete" if dry_run else "Deleted"
        anonymous_msg = (
            f", {anonymous_count} anonymous"
            if options["purge_anonymous"]
            else ""
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode} {total_count} carts "
                f"({expired_count} expired, {stale_count} stale before "
                f"{stale_cutoff.date()} [{stale_anonymous_count} anonymous, "
                f"{stale_linked_count} user-linked]{anonymous_msg}, "
                f"{closed_carts_count} from closed/expired leads)"
            )
        )
