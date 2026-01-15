"""
Django management command to fix product visibility.

This command ensures all inventory units are set to:
- sale_status = 'AV' (AVAILABLE)
- available_online = True

And all products are published.

Usage:
    python manage.py fix_product_visibility
"""
from django.core.management.base import BaseCommand
from django.db.models import Q, Sum, Count
from inventory.models import Product, InventoryUnit


class Command(BaseCommand):
    help = 'Fix product visibility by setting all units to AVAILABLE and available_online=True'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
        
        # 1. Fix inventory units
        self.stdout.write('1. Checking inventory units...')
        units_to_fix = InventoryUnit.objects.filter(
            ~Q(sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE) | 
            ~Q(available_online=True)
        )
        
        self.stdout.write(f"  Found {units_to_fix.count()} units that need fixing")
        
        fixed_count = 0
        # Use bulk_update for better performance
        units_to_update = []
        for unit in units_to_fix:
            changed = False
            if unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
                old_status = unit.get_sale_status_display()
                self.stdout.write(f"  Unit {unit.id} ({unit.product_template.product_name}): sale_status {old_status} → AVAILABLE")
                unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                changed = True
            
            if not unit.available_online:
                self.stdout.write(f"  Unit {unit.id} ({unit.product_template.product_name}): available_online False → True")
                unit.available_online = True
                changed = True
            
            if changed:
                units_to_update.append(unit)
                fixed_count += 1
        
        if units_to_update and not dry_run:
            InventoryUnit.objects.bulk_update(units_to_update, ['sale_status', 'available_online'])
            self.stdout.write(self.style.SUCCESS(f'  ✅ Fixed {fixed_count} units'))
        elif fixed_count > 0:
            self.stdout.write(self.style.WARNING(f'  Would fix {fixed_count} units (dry run)'))
        
        
        # 2. Ensure products are published
        self.stdout.write('2. Checking products...')
        unpublished = Product.objects.filter(is_published=False, is_discontinued=False)
        
        if unpublished.exists():
            count = unpublished.count()
            if dry_run:
                self.stdout.write(self.style.WARNING(f'  Would publish {count} products'))
            else:
                unpublished.update(is_published=True)
                self.stdout.write(self.style.SUCCESS(f'  ✅ Published {count} products'))
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ All products are already published'))
        self.stdout.write('')
        
        # 3. Verify
        self.stdout.write('3. Verification...')
        available_units = InventoryUnit.objects.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        )
        self.stdout.write(f'  Available & online units: {available_units.count()}')
        
        products = Product.objects.filter(is_published=True, is_discontinued=False)
        self.stdout.write(f'  Published products: {products.count()}')
        
        # Count products with available units
        products_with_units = 0
        for product in products:
            units = product.inventory_units.filter(
                sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                available_online=True
            )
            if product.product_type == Product.ProductType.ACCESSORY:
                count = units.aggregate(total=Sum('quantity'))['total'] or 0
            else:
                count = units.count()
            if count > 0:
                products_with_units += 1
        
        self.stdout.write(f'  Products with available units: {products_with_units}')
        self.stdout.write('')
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS('=' * 80))
            self.stdout.write(self.style.SUCCESS('FIX COMPLETE!'))
            self.stdout.write(self.style.SUCCESS('=' * 80))
            self.stdout.write('')
            self.stdout.write('Your products should now appear in the frontend.')
            self.stdout.write('Refresh your browser to see the changes.')
        else:
            self.stdout.write(self.style.WARNING('=' * 80))
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETE'))
            self.stdout.write(self.style.WARNING('=' * 80))
            self.stdout.write('')
            self.stdout.write('Run without --dry-run to apply changes.')
