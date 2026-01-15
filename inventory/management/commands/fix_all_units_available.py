"""
Quick fix: Set all inventory units to AVAILABLE and available_online=True
This is a one-time fix for units that should be available but aren't.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from inventory.models import InventoryUnit


class Command(BaseCommand):
    help = 'Set all inventory units to AVAILABLE status and available_online=True'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        # Find all units that are not available or not available_online
        units_to_fix = InventoryUnit.objects.filter(
            ~Q(sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE) |
            Q(available_online=False)
        )
        
        total_count = units_to_fix.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ All units are already available!\n'))
            return
        
        self.stdout.write(f'\nFound {total_count} units that need fixing:\n')
        
        # Show breakdown
        status_breakdown = {}
        for unit in units_to_fix[:20]:  # Sample first 20
            key = f"status={unit.sale_status}, online={unit.available_online}"
            status_breakdown[key] = status_breakdown.get(key, 0) + 1
        
        for key, count in status_breakdown.items():
            self.stdout.write(f"  {key}: {count} units")
        
        if total_count > 20:
            self.stdout.write(f"  ... and {total_count - 20} more\n")
        
        if not dry_run:
            # Fix all units
            updated = InventoryUnit.objects.filter(
                ~Q(sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE) |
                Q(available_online=False)
            ).update(
                sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                available_online=True
            )
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ Fixed {updated} units!\n'))
            self.stdout.write('   All units are now AVAILABLE and available_online=True\n')
            self.stdout.write('   Products should now be visible on the frontend.\n')
        else:
            self.stdout.write(self.style.WARNING(f'\n💡 DRY RUN: Would fix {total_count} units\n'))
            self.stdout.write('   Run without --dry-run to actually update them.\n')
