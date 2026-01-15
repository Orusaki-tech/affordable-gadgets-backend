"""
Management command to fix product visibility by ensuring inventory units are available.
This command will:
1. Show current unit statuses
2. Optionally fix units that should be available but aren't
"""
from django.core.management.base import BaseCommand
from inventory.models import Product, InventoryUnit


class Command(BaseCommand):
    help = 'Fix product visibility by checking and updating inventory unit statuses'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Actually update units (default is dry-run)',
        )
        parser.add_argument(
            '--product-id',
            type=int,
            help='Fix only a specific product ID',
        )

    def handle(self, *args, **options):
        fix = options['fix']
        product_id = options.get('product_id')
        
        if product_id:
            products = Product.objects.filter(id=product_id, is_published=True, is_discontinued=False)
        else:
            products = Product.objects.filter(is_published=True, is_discontinued=False)
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"Checking {products.count()} published products...")
        self.stdout.write(f"{'='*60}\n")
        
        total_units_checked = 0
        units_to_fix = []
        products_with_issues = []
        
        for product in products:
            units = product.inventory_units.all()
            total_units_checked += units.count()
            
            available_count = units.filter(sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE).count()
            available_online_count = units.filter(
                sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
                available_online=True
            ).count()
            
            if available_online_count == 0 and units.exists():
                # Product has units but none are available online
                products_with_issues.append(product)
                
                # Check what statuses the units actually have
                status_breakdown = {}
                for unit in units:
                    status_key = f"{unit.sale_status}_{unit.available_online}"
                    status_breakdown[status_key] = status_breakdown.get(status_key, 0) + 1
                
                self.stdout.write(f"\n⚠️  Product: {product.product_name} (ID: {product.id})")
                self.stdout.write(f"   Total units: {units.count()}")
                self.stdout.write(f"   Available: {available_count}")
                self.stdout.write(f"   Available online: {available_online_count}")
                self.stdout.write(f"   Status breakdown: {status_breakdown}")
                
                # Find units that should be available but aren't
                for unit in units:
                    if unit.sale_status != InventoryUnit.SaleStatusChoices.AVAILABLE:
                        units_to_fix.append({
                            'unit': unit,
                            'issue': f"Status is {unit.get_sale_status_display()} (should be AVAILABLE)",
                            'action': 'set_status_available'
                        })
                    elif not unit.available_online:
                        units_to_fix.append({
                            'unit': unit,
                            'issue': f"available_online is False (should be True)",
                            'action': 'set_available_online'
                        })
        
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"SUMMARY:")
        self.stdout.write(f"  Products checked: {products.count()}")
        self.stdout.write(f"  Total units checked: {total_units_checked}")
        self.stdout.write(f"  Products with visibility issues: {len(products_with_issues)}")
        self.stdout.write(f"  Units that need fixing: {len(units_to_fix)}")
        self.stdout.write(f"{'='*60}\n")
        
        if units_to_fix:
            if fix:
                self.stdout.write(f"\n🔧 FIXING {len(units_to_fix)} units...\n")
                fixed_count = 0
                for item in units_to_fix:
                    unit = item['unit']
                    action = item['action']
                    
                    if action == 'set_status_available':
                        old_status = unit.sale_status
                        unit.sale_status = InventoryUnit.SaleStatusChoices.AVAILABLE
                        unit.save(update_fields=['sale_status'])
                        self.stdout.write(f"  ✓ Unit {unit.id}: Changed status from {old_status} to AVAILABLE")
                        fixed_count += 1
                    elif action == 'set_available_online':
                        unit.available_online = True
                        unit.save(update_fields=['available_online'])
                        self.stdout.write(f"  ✓ Unit {unit.id}: Set available_online=True")
                        fixed_count += 1
                
                self.stdout.write(f"\n✅ Fixed {fixed_count} units!")
                self.stdout.write(f"   Products should now be visible on the frontend.\n")
            else:
                self.stdout.write(f"\n💡 DRY RUN: Found {len(units_to_fix)} units that need fixing.")
                self.stdout.write(f"   Run with --fix to actually update them.\n")
        else:
            self.stdout.write(f"\n✅ No issues found! All products should be visible.\n")
