"""
Management command to check storage_gb values in database and API response.
Usage: python manage.py check_storage_gb [product_id]
"""
from django.core.management.base import BaseCommand
from django.test import RequestFactory
from inventory.models import InventoryUnit, Product
from inventory.serializers_public import PublicInventoryUnitSerializer
from inventory.views_public import PublicProductViewSet
import json


class Command(BaseCommand):
    help = 'Check storage_gb values in database and compare with API response'

    def add_arguments(self, parser):
        parser.add_argument(
            'product_id',
            type=int,
            nargs='?',
            help='Product ID to check (optional, will check first product if not provided)'
        )

    def handle(self, *args, **options):
        product_id = options.get('product_id')
        
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('CHECKING STORAGE_GB IN DATABASE AND API'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        
        # Get product
        if product_id:
            try:
                product = Product.objects.get(pk=product_id, is_published=True)
            except Product.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'❌ Product {product_id} not found or not published'))
                return
        else:
            # Get first published product
            product = Product.objects.filter(is_published=True).first()
            if not product:
                self.stdout.write(self.style.ERROR('❌ No published products found'))
                return
            product_id = product.id
        
        self.stdout.write(f'\n📦 Product: {product.product_name} (ID: {product_id})')
        self.stdout.write(f'   Type: {product.product_type}')
        
        # Check database values
        self.stdout.write(self.style.SUCCESS('\n' + '-' * 80))
        self.stdout.write(self.style.SUCCESS('DATABASE VALUES'))
        self.stdout.write(self.style.SUCCESS('-' * 80))
        
        units = InventoryUnit.objects.filter(
            product_template=product,
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        ).select_related('product_color', 'product_template')
        
        self.stdout.write(f'\nTotal available units: {units.count()}')
        
        units_with_storage = units.filter(storage_gb__isnull=False)
        units_without_storage = units.filter(storage_gb__isnull=True)
        
        self.stdout.write(f'  ✅ Units WITH storage_gb: {units_with_storage.count()}')
        self.stdout.write(f'  ❌ Units WITHOUT storage_gb: {units_without_storage.count()}')
        
        if units_with_storage.exists():
            self.stdout.write('\n  Units with storage:')
            for unit in units_with_storage[:10]:
                self.stdout.write(f'    - Unit ID: {unit.id}, Storage: {unit.storage_gb}GB, Price: {unit.selling_price}, Color: {unit.color_name or "N/A"}')
        
        if units_without_storage.exists():
            self.stdout.write('\n  Units without storage:')
            for unit in units_without_storage[:10]:
                self.stdout.write(f'    - Unit ID: {unit.id}, Price: {unit.selling_price}, Color: {unit.color_name or "N/A"}')
        
        # Check API response
        self.stdout.write(self.style.SUCCESS('\n' + '-' * 80))
        self.stdout.write(self.style.SUCCESS('API RESPONSE'))
        self.stdout.write(self.style.SUCCESS('-' * 80))
        
        # Create a mock request
        factory = RequestFactory()
        request = factory.get(f'/api/v1/public/products/{product_id}/units/')
        request.brand = None  # No brand filtering for this test
        
        # Get units using the same logic as the API endpoint
        api_units = product.inventory_units.filter(
            sale_status=InventoryUnit.SaleStatusChoices.AVAILABLE,
            available_online=True
        ).select_related('product_color', 'product_template')
        
        # Serialize using the public serializer
        serializer = PublicInventoryUnitSerializer(
            api_units,
            many=True,
            context={'request': request, 'brand': None}
        )
        
        serialized_data = serializer.data
        
        self.stdout.write(f'\nTotal units in API response: {len(serialized_data)}')
        
        api_units_with_storage = [u for u in serialized_data if u.get('storage_gb') is not None]
        api_units_without_storage = [u for u in serialized_data if u.get('storage_gb') is None]
        
        self.stdout.write(f'  ✅ Units WITH storage_gb in API: {len(api_units_with_storage)}')
        self.stdout.write(f'  ❌ Units WITHOUT storage_gb in API: {len(api_units_without_storage)}')
        
        if api_units_with_storage:
            self.stdout.write('\n  Units with storage in API response:')
            for unit in api_units_with_storage[:10]:
                self.stdout.write(f'    - Unit ID: {unit.get("id")}, Storage: {unit.get("storage_gb")}GB, Price: {unit.get("selling_price")}, Color: {unit.get("color_name") or "N/A"}')
        
        if api_units_without_storage:
            self.stdout.write('\n  Units without storage in API response:')
            for unit in api_units_without_storage[:10]:
                self.stdout.write(f'    - Unit ID: {unit.get("id")}, Price: {unit.get("selling_price")}, Color: {unit.get("color_name") or "N/A"}')
                # Check if storage_gb field exists at all
                if 'storage_gb' not in unit:
                    self.stdout.write(self.style.WARNING(f'      ⚠️  WARNING: storage_gb field is MISSING from response!'))
                elif unit.get('storage_gb') is None:
                    self.stdout.write(f'      ℹ️  storage_gb field exists but is NULL')
        
        # Comparison
        self.stdout.write(self.style.SUCCESS('\n' + '-' * 80))
        self.stdout.write(self.style.SUCCESS('COMPARISON'))
        self.stdout.write(self.style.SUCCESS('-' * 80))
        
        db_count = units_with_storage.count()
        api_count = len(api_units_with_storage)
        
        if db_count == api_count:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Database and API match: {db_count} units with storage'))
        else:
            self.stdout.write(self.style.ERROR(f'\n❌ MISMATCH: Database has {db_count} units with storage, API returns {api_count}'))
        
        # Show sample JSON
        if serialized_data:
            self.stdout.write(self.style.SUCCESS('\n' + '-' * 80))
            self.stdout.write(self.style.SUCCESS('SAMPLE API RESPONSE (First Unit)'))
            self.stdout.write(self.style.SUCCESS('-' * 80))
            sample = serialized_data[0]
            self.stdout.write(json.dumps(sample, indent=2))
        
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))

