"""Management command to clean up expired carts."""
from django.core.management.base import BaseCommand
from inventory.models import Cart, Lead
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Clean up expired carts and carts for closed/expired leads (after 7 day grace period)'
    
    def handle(self, *args, **options):
        now = timezone.now()
        grace_period = timedelta(days=7)
        
        # 1. Clean up unsubmitted expired carts
        expired_carts = Cart.objects.filter(
            is_submitted=False,
            expires_at__lt=now
        )
        expired_count = expired_carts.count()
        expired_carts.delete()
        
        # 2. Clean up carts for closed/expired leads (after 7 day grace period)
        # These carts are kept for reference but can be cleaned up after grace period
        closed_expired_leads = Lead.objects.filter(
            status__in=[Lead.StatusChoices.CLOSED, Lead.StatusChoices.EXPIRED],
            submitted_at__lt=now - grace_period
        )
        
        closed_carts_count = 0
        for lead in closed_expired_leads:
            try:
                cart = Cart.objects.filter(lead=lead).first()
                if cart:
                    cart.delete()
                    closed_carts_count += 1
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not delete cart for lead {lead.lead_reference}: {str(e)}')
                )
        
        total_count = expired_count + closed_carts_count
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully deleted {total_count} carts '
                f'({expired_count} expired, {closed_carts_count} from closed/expired leads)'
            )
        )

