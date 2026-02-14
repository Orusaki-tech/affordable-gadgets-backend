"""
Management command to delete every product and optionally recreate them with dummy data.
Deletes in dependency order: orders, carts, leads, reservations, returns, transfers,
bundles, inventory units, product images/accessories, then products.
"""
from django.core.management.base import BaseCommand

from inventory.models import (
    AuditLog,
    Bundle,
    BundleItem,
    Cart,
    CartItem,
    InventoryUnit,
    InventoryUnitImage,
    Lead,
    LeadItem,
    Notification,
    Order,
    OrderItem,
    Product,
    ProductAccessory,
    ProductImage,
    Promotion,
    ReservationRequest,
    ReturnRequest,
    Review,
    UnitTransfer,
    WishlistItem,
)


class Command(BaseCommand):
    help = 'Delete every product (and dependent data) and optionally recreate with dummy data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recreate-dummy',
            action='store_true',
            help='After deleting, recreate products and inventory units using generate_dummy_data logic',
        )
        parser.add_argument(
            '--products',
            type=int,
            default=30,
            help='Number of products to create when using --recreate-dummy (default: 30)',
        )
        parser.add_argument(
            '--units-per-product',
            type=int,
            default=8,
            help='Number of units per product when using --recreate-dummy (default: 8)',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Deleting all product-related data...'))
        self._delete_all_product_data()
        self.stdout.write(self.style.SUCCESS('All products and related data deleted.'))

        if options['recreate_dummy']:
            self.stdout.write('Recreating products and units with dummy data...')
            self._recreate_dummy(
                num_products=options['products'],
                units_per_product=options['units_per_product'],
            )
            self.stdout.write(self.style.SUCCESS('Done. Products and units recreated.'))

    def _delete_all_product_data(self):
        """Delete all data that depends on Product or InventoryUnit, in safe order."""
        # Order matters: respect PROTECT FKs (InventoryUnit -> Product, Bundle/BundleItem -> Product)
        AuditLog.objects.all().delete()
        Notification.objects.all().delete()
        CartItem.objects.all().delete()
        Cart.objects.all().delete()
        LeadItem.objects.all().delete()
        Lead.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        UnitTransfer.objects.all().delete()
        ReturnRequest.objects.all().delete()
        ReservationRequest.objects.all().delete()
        Review.objects.all().delete()
        Promotion.objects.all().delete()
        # Bundles reference Product (PROTECT)
        BundleItem.objects.all().delete()
        Bundle.objects.all().delete()
        ProductAccessory.objects.all().delete()
        InventoryUnitImage.objects.all().delete()
        InventoryUnit.objects.all().delete()
        ProductImage.objects.all().delete()
        WishlistItem.objects.all().delete()
        Product.objects.all().delete()

    def _recreate_dummy(self, num_products=30, units_per_product=8):
        """Reuse generate_dummy_data to create products and units (no orders/carts/etc)."""
        from inventory.management.commands.generate_dummy_data import Command as DummyDataCommand

        cmd = DummyDataCommand()
        cmd.stdout = self.stdout
        cmd.style = self.style
        cmd._ensure_prerequisites()
        brands = cmd._ensure_brands()
        colors = cmd._ensure_colors()
        tags = cmd._ensure_tags()
        admin_roles = cmd._ensure_admin_roles()
        admins = cmd._ensure_admins(admin_roles, brands)
        cmd._ensure_customers()
        sources = cmd._ensure_acquisition_sources()
        cmd._ensure_promotion_types()

        products = cmd._create_products(num_products, tags, brands, admins)
        units = cmd._create_units(products, units_per_product, colors, sources)
        cmd._create_product_images(products)
        cmd._create_unit_images(units, colors)
        cmd._create_accessories(products)
