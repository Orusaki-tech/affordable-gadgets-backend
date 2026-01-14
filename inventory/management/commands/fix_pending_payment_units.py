"""
Management command to fix inventory units that are still in PENDING_PAYMENT
status even though their orders are PAID.

Usage:
    python manage.py fix_pending_payment_units
    python manage.py fix_pending_payment_units --dry-run
"""
from django.core.management.base import BaseCommand
from inventory.models import Order, InventoryUnit, OrderItem
from django.db import transaction


class Command(BaseCommand):
    help = 'Fix inventory units that are PENDING_PAYMENT but their orders are PAID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually doing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made\n'))
        
        # Find all PAID orders
        paid_orders = Order.objects.filter(status=Order.StatusChoices.PAID)
        self.stdout.write(f'Found {paid_orders.count()} paid orders\n')
        
        total_units_fixed = 0
        orders_processed = 0
        
        for order in paid_orders:
            order_items = order.order_items.all()
            units_to_fix = []
            
            for order_item in order_items:
                unit = order_item.inventory_unit
                if unit and unit.sale_status == InventoryUnit.SaleStatusChoices.PENDING_PAYMENT:
                    units_to_fix.append(unit)
            
            if units_to_fix:
                orders_processed += 1
                self.stdout.write(f'\nOrder {order.order_id} ({order.status}):')
                self.stdout.write(f'  Found {len(units_to_fix)} units in PENDING_PAYMENT status')
                
                for unit in units_to_fix:
                    self.stdout.write(f'    - Unit {unit.id}: {unit.product_template.product_name if unit.product_template else "N/A"}')
                    
                    if not dry_run:
                        with transaction.atomic():
                            unit.sale_status = InventoryUnit.SaleStatusChoices.SOLD
                            unit.save(update_fields=['sale_status'])
                            total_units_fixed += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'      ✓ Updated to SOLD')
                            )
                    else:
                        self.stdout.write(
                            self.style.WARNING(f'      → Would update to SOLD')
                        )
                        total_units_fixed += 1
        
        self.stdout.write(f'\n{"="*60}')
        if dry_run:
            self.stdout.write(self.style.WARNING(f'DRY RUN: Would fix {total_units_fixed} units in {orders_processed} orders'))
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✅ Fixed {total_units_fixed} units in {orders_processed} orders')
            )
        self.stdout.write(f'{"="*60}\n')

