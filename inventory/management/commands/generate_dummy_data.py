"""
Management command to generate comprehensive dummy data for ALL database tables.
Creates: Products, Units, Reviews, Reservation Requests, Return Requests, Unit Transfers,
Orders, Leads, Carts, Promotions, Notifications, Audit Logs, and more.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.core.files import File
from django.core.files.temp import NamedTemporaryFile
from datetime import timedelta
from decimal import Decimal
import random
import string
import uuid
import os
from pathlib import Path

# Try to import requests, but make it optional
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from inventory.models import (
    Product, InventoryUnit, Review, ReservationRequest, ReturnRequest, UnitTransfer,
    Admin, AdminRole, Customer, Brand, Color, Tag, ProductImage, InventoryUnitImage,
    UnitAcquisitionSource, Order, OrderItem, Lead, LeadItem, Cart, CartItem,
    Promotion, PromotionType, Notification, AuditLog, ProductAccessory,
    Bundle, BundleItem, WishlistItem,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate comprehensive dummy data for ALL database tables'

    def add_arguments(self, parser):
        parser.add_argument(
            '--products',
            type=int,
            default=30,
            help='Number of products to create (default: 30)',
        )
        parser.add_argument(
            '--units-per-product',
            type=int,
            default=8,
            help='Number of units per product (default: 8)',
        )
        parser.add_argument(
            '--reviews',
            type=int,
            default=80,
            help='Number of reviews to create (default: 80)',
        )
        parser.add_argument(
            '--reservations',
            type=int,
            default=20,
            help='Number of reservation requests to create (default: 20)',
        )
        parser.add_argument(
            '--returns',
            type=int,
            default=15,
            help='Number of return requests to create (default: 15)',
        )
        parser.add_argument(
            '--transfers',
            type=int,
            default=15,
            help='Number of unit transfers to create (default: 15)',
        )
        parser.add_argument(
            '--orders',
            type=int,
            default=25,
            help='Number of orders to create (default: 25)',
        )
        parser.add_argument(
            '--leads',
            type=int,
            default=30,
            help='Number of leads to create (default: 30)',
        )
        parser.add_argument(
            '--carts',
            type=int,
            default=20,
            help='Number of carts to create (default: 20)',
        )
        parser.add_argument(
            '--promotions',
            type=int,
            default=10,
            help='Number of promotions to create (default: 10)',
        )
        parser.add_argument(
            '--notifications',
            type=int,
            default=50,
            help='Number of notifications to create (default: 50)',
        )
        parser.add_argument(
            '--audit-logs',
            type=int,
            default=100,
            help='Number of audit logs to create (default: 100)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before generating new data',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting comprehensive dummy data generation...'))
        
        if options['clear']:
            self.stdout.write(self.style.WARNING('⚠️  Clearing existing data...'))
            self._clear_data()
        
        # Ensure prerequisites exist
        self._ensure_prerequisites()
        
        # Generate data in order of dependencies
        brands = self._ensure_brands()
        colors = self._ensure_colors()
        tags = self._ensure_tags()
        admin_roles = self._ensure_admin_roles()
        admins = self._ensure_admins(admin_roles, brands)
        customers = self._ensure_customers()
        sources = self._ensure_acquisition_sources()
        promotion_types = self._ensure_promotion_types()
        
        products = self._create_products(options['products'], tags, brands, admins)
        units = self._create_units(products, options['units_per_product'], colors, sources)
        product_images = self._create_product_images(products)
        unit_images = self._create_unit_images(units, colors)
        accessories = self._create_accessories(products)
        reviews = self._create_reviews(products, customers, options['reviews'])
        promotions = self._create_promotions(brands, promotion_types, products, admins, options['promotions'])
        reservations = self._create_reservation_requests(admins, units, options['reservations'])
        returns = self._create_return_requests(admins, units, options['returns'])
        transfers = self._create_unit_transfers(admins, units, options['transfers'])
        orders = self._create_orders(customers, brands, units, options['orders'])
        leads = self._create_leads(customers, brands, units, admins, options['leads'])
        carts = self._create_carts(customers, brands, units, promotions, options['carts'])
        notifications = self._create_notifications(admins, customers, reservations, returns, transfers, options['notifications'])
        audit_logs = self._create_audit_logs(admins, customers, options['audit_logs'])
        
        self.stdout.write(self.style.SUCCESS('\n✅ Dummy data generation complete!'))
        self._print_summary()

    def _clear_data(self):
        """Clear existing dummy data"""
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
        BundleItem.objects.all().delete()
        Bundle.objects.all().delete()
        ProductAccessory.objects.all().delete()
        WishlistItem.objects.all().delete()
        InventoryUnitImage.objects.all().delete()
        InventoryUnit.objects.all().delete()
        ProductImage.objects.all().delete()
        Product.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('✓ Existing data cleared.'))

    def _ensure_prerequisites(self):
        """Ensure basic prerequisites exist"""
        self.stdout.write('📋 Checking prerequisites...')

    def _ensure_brands(self):
        """Ensure brands exist"""
        brands_data = [
            {'code': 'AFFORDABLE_GADGETS', 'name': 'Affordable Gadgets', 'description': 'Main brand'},
            {'code': 'PREMIUM', 'name': 'Premium Phones', 'description': 'Premium brand'},
            {'code': 'BUDGET', 'name': 'Budget Phones', 'description': 'Budget-friendly brand'},
        ]
        brands = []
        for brand_data in brands_data:
            brand, _ = Brand.objects.get_or_create(
                code=brand_data['code'],
                defaults=brand_data
            )
            brands.append(brand)
        return brands

    def _ensure_colors(self):
        """Create colors"""
        colors_data = [
            ('Black', '#000000'), ('White', '#FFFFFF'), ('Blue', '#0000FF'),
            ('Red', '#FF0000'), ('Gold', '#FFD700'), ('Silver', '#C0C0C0'),
            ('Purple', '#800080'), ('Green', '#008000'), ('Pink', '#FFC0CB'),
            ('Gray', '#808080'), ('Orange', '#FFA500')
        ]
        colors = []
        for name, hex_code in colors_data:
            color, _ = Color.objects.get_or_create(
                name=name,
                defaults={'hex_code': hex_code}
            )
            colors.append(color)
        return colors

    def _ensure_tags(self):
        """Create tags"""
        tag_names = ['Premium', 'Best Seller', 'New Arrival', 'On Sale', 'Featured', 'Popular', 'Limited Edition']
        tags = []
        for name in tag_names:
            tag, _ = Tag.objects.get_or_create(name=name)
            tags.append(tag)
        return tags

    def _ensure_admin_roles(self):
        """Ensure admin roles exist"""
        roles = AdminRole.RoleChoices
        role_objects = []
        for role_code, role_label in [
            (roles.SALESPERSON, 'Salesperson'),
            (roles.INVENTORY_MANAGER, 'Inventory Manager'),
            (roles.CONTENT_CREATOR, 'Content Creator'),
            (roles.ORDER_MANAGER, 'Order Manager'),
            (roles.MARKETING_MANAGER, 'Marketing Manager'),
        ]:
            role, _ = AdminRole.objects.get_or_create(
                name=role_code,
                defaults={
                    'display_name': role_label,
                    'description': f'{role_label} role'
                }
            )
            role_objects.append(role)
        return role_objects

    def _ensure_admins(self, roles, brands):
        """Create admins with different roles"""
        admins = []
        role_mapping = {
            'SP': AdminRole.RoleChoices.SALESPERSON,
            'IM': AdminRole.RoleChoices.INVENTORY_MANAGER,
            'CC': AdminRole.RoleChoices.CONTENT_CREATOR,
            'OM': AdminRole.RoleChoices.ORDER_MANAGER,
            'MM': AdminRole.RoleChoices.MARKETING_MANAGER,
        }
        
        for role_code, role_choice in role_mapping.items():
            # Create 2-3 admins per role
            for i in range(2 if role_code == 'IM' else 3):
                username = f'{role_code.lower()}_admin_{i+1}'
                user, _ = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'email': f'{username}@shwari.com',
                        'first_name': role_choice.label.split()[0],
                        'last_name': f'Admin{i+1}'
                    }
                )
                
                admin, _ = Admin.objects.get_or_create(
                    user=user,
                    defaults={'admin_code': f'{role_code}{i+1}'}
                )
                role_obj = roles[list(role_mapping.keys()).index(role_code)]
                admin.roles.add(role_obj)
                if brands:
                    admin.brands.add(random.choice(brands))
                admin.save()
                admins.append(admin)
        
        return admins

    def _ensure_customers(self):
        """Create customers"""
        customers = []
        for i in range(25):
            username = f'customer_{i+1}'
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@example.com',
                    'first_name': f'Customer',
                    'last_name': f'{i+1}'
                }
            )
            customer, _ = Customer.objects.get_or_create(
                user=user,
                defaults={
                    'name': f'Customer {i+1}',
                    'phone': f'+2547123456{i:02d}',
                    'email': f'{username}@example.com',
                    'delivery_address': f'{random.randint(100, 999)} Main Street, Nairobi'
                }
            )
            customers.append(customer)
        return customers

    def _ensure_acquisition_sources(self):
        """Create acquisition sources"""
        sources = []
        suppliers = ['Tech Suppliers Ltd', 'Global Imports Inc', 'Mobile World Co', 'Phone Distributors']
        for name in suppliers:
            source, _ = UnitAcquisitionSource.objects.get_or_create(
                name=name,
                defaults={
                    'source_type': random.choice(['SU', 'IM']),
                    'phone_number': f'+2547{random.randint(10000000, 99999999)}'
                }
            )
            sources.append(source)
        return sources

    def _ensure_promotion_types(self):
        """Ensure promotion types exist"""
        types_data = [
            {'name': 'Special Offer', 'code': 'SO', 'description': 'General special offers and discounts'},
            {'name': 'Flash Sale', 'code': 'FS', 'description': 'Limited-time flash sales with urgent discounts'},
            {'name': 'New Arrival', 'code': 'NA', 'description': 'Promotions for newly arrived products'},
            {'name': 'Weekend Deal', 'code': 'WD', 'description': 'Special weekend promotions'},
            {'name': 'Bundle Deal', 'code': 'BD', 'description': 'Bundle promotions for multiple products'},
            {'name': 'Clearance Sale', 'code': 'CL', 'description': 'Clearance sales for discontinued or excess inventory'},
        ]
        types = []
        for type_data in types_data:
            promo_type, _ = PromotionType.objects.get_or_create(
                code=type_data['code'],
                defaults={
                    'name': type_data['name'],
                    'description': type_data.get('description', f'{type_data["name"]} promotion'),
                    'is_active': True,
                    'display_order': len(types) + 1
                }
            )
            types.append(promo_type)
        return types

    def _create_products(self, count, tags, brands, admins):
        """Create products with all fields"""
        products = []
        brands_list = ['Apple', 'Samsung', 'Tecno', 'Xiaomi', 'Huawei', 'Oppo', 'Vivo', 'OnePlus', 'Infinix', 'Realme']
        models_data = {
            'Apple': ['iPhone 15 Pro', 'iPhone 14', 'iPhone 13', 'iPhone 12', 'iPhone 11'],
            'Samsung': ['Galaxy S24 Ultra', 'Galaxy S23', 'Galaxy A54', 'Galaxy Note 20', 'Galaxy A34'],
            'Tecno': ['Camon 20', 'Spark 10', 'Phantom X2', 'Pova 5'],
            'Xiaomi': ['Redmi Note 12', 'Mi 13', 'POCO X5', 'Redmi 10'],
        }
        product_types = ['PH', 'LT', 'TB', 'AC']
        type_names = {'PH': 'Phone', 'LT': 'Laptop', 'TB': 'Tablet', 'AC': 'Accessory'}
        
        for i in range(count):
            brand = random.choice(brands_list)
            model_list = models_data.get(brand, ['Model X', 'Model Y'])
            model = random.choice(model_list)
            product_type = random.choice(product_types)
            
            if product_type != 'AC':
                product_name = f"{brand} {model}"
                slug = slugify(f"{brand}-{model}-{i+1}")
            else:
                accessory_type = random.choice(['Charger', 'Case', 'Screen Protector', 'Earbuds', 'Power Bank'])
                product_name = f"{brand} {accessory_type}"
                slug = slugify(f"{brand}-{accessory_type}-{i+1}")
            
            # Ensure slug is unique
            base_slug = slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            # Get a content creator or admin for created_by/updated_by
            # Note: We need to get admins after they're created, so we'll handle this after creation
            product = Product.objects.create(
                product_type=product_type,
                product_name=product_name,
                brand=brand,
                model_series=model,
                product_description=f"High-quality {type_names[product_type]} with advanced features. Perfect for everyday use.",
                min_stock_threshold=5,
                reorder_point=10,
                is_discontinued=random.choice([True, False, False, False]),
                is_published=random.choice([True, True, True, False]),
                slug=slug,
                meta_title=f"{product_name} - Best {type_names[product_type]} Deals",
                meta_description=f"Shop {product_name} at Affordable Gadgets. Best prices and quality guaranteed.",
                keywords=f"{brand}, {model}, {type_names[product_type]}, smartphone, mobile",
                product_highlights=[
                    "High-quality display",
                    "Long battery life",
                    "Fast processor",
                    "Great camera",
                    "Premium design"
                ],
                long_description=f"Experience the power of {product_name}. This {type_names[product_type]} features cutting-edge technology and premium design. Perfect for work and play.",
                # Video URL logic: accessories get 40% chance, other products get varying chances
                product_video_url=f"https://www.youtube.com/watch?v=dQw4w9WgXcQ" if (
                    (product_type == 'AC' and random.choice([True, True, False, False, False])) or
                    (product_type != 'AC' and ((i < 15 and random.choice([True, True, False])) or (i >= 15 and random.choice([True, False, False, False]))))
                ) else None,
            )
            
            # Set created_by and updated_by after creation (need admins to exist)
            if admins:
                content_creators = [a for a in admins if a.has_role(AdminRole.RoleChoices.CONTENT_CREATOR)]
                creator = random.choice(content_creators) if content_creators else random.choice(admins)
                product.created_by = creator.user
                product.updated_by = creator.user
                product.save()
            
            # Add tags
            selected_tags = random.sample(tags, random.randint(1, 3))
            product.tags.set(selected_tags)
            
            # Add brand association
            if brands:
                product.brands.add(random.choice(brands))
            
            products.append(product)
            if (i + 1) % 10 == 0:
                self.stdout.write(f'  ✓ Created {i+1}/{count} products')
        
        return products

    def _create_units(self, products, units_per_product, colors, sources):
        """Create inventory units"""
        conditions = ['N', 'R', 'P']
        grades = ['A', 'B', None]
        sources_list = ['SU', 'IM', 'BB']
        storage_options = [64, 128, 256, 512, 1024]
        ram_options = [4, 6, 8, 12, 16]
        battery_options = [3000, 4000, 5000, 6000, 7000]
        processors = ['Snapdragon 8 Gen 2', 'A17 Pro', 'Exynos 2400', 'MediaTek Dimensity 9200', 'Apple M2']
        statuses = ['AV', 'AV', 'AV', 'RS', 'SD', 'PP']  # More available than reserved/sold
        
        units = []
        total = len(products) * units_per_product
        
        for idx, product in enumerate(products):
            for unit_num in range(units_per_product):
                condition = random.choice(conditions)
                grade = random.choice(grades) if condition != 'N' else None
                color = random.choice(colors) if colors else None
                status = random.choice(statuses)
                
                # Generate unique serial number
                serial = f"{product.brand[:3].upper()}{random.randint(100000, 999999)}"
                
                # Calculate price
                base_price = random.randint(20000, 150000)
                if condition == 'N':
                    price = base_price
                elif condition == 'R':
                    price = int(base_price * 0.8)
                else:
                    price = int(base_price * 0.6)
                
                unit = InventoryUnit.objects.create(
                    product_template=product,
                    selling_price=price,
                    cost_of_unit=int(price * 0.7),
                    condition=condition,
                    grade=grade,
                    source=random.choice(sources_list),
                    sale_status=status,
                    serial_number=serial if product.product_type != 'AC' else None,
                    imei=f"{random.randint(100000000000000, 999999999999999)}" if product.product_type == 'PH' else None,
                    storage_gb=random.choice(storage_options) if product.product_type in ['PH', 'LT', 'TB'] else None,
                    ram_gb=random.choice(ram_options) if product.product_type in ['PH', 'LT', 'TB'] else None,
                    battery_mah=random.choice(battery_options) if product.product_type in ['PH', 'TB'] else None,
                    processor_details=random.choice(processors) if product.product_type == 'LT' else '',
                    product_color=color,
                    quantity=1 if product.product_type != 'AC' else random.randint(1, 10),
                    date_sourced=timezone.now().date() - timedelta(days=random.randint(1, 365)),
                    acquisition_source_details=random.choice(sources) if sources and random.choice([True, False]) else None,
                    available_online=random.choice([True, True, False])
                )
                
                # Reserve unit if status is RS
                if status == 'RS' and product.product_type != 'AC':
                    salespersons = Admin.objects.filter(roles__name=AdminRole.RoleChoices.SALESPERSON)
                    if salespersons.exists():
                        unit.reserved_by = random.choice(list(salespersons))
                        unit.reserved_until = timezone.now() + timedelta(days=random.randint(1, 2))
                        unit.save()
                
                units.append(unit)
            
            if (idx + 1) % 5 == 0:
                self.stdout.write(f'  ✓ Created units for {idx+1}/{len(products)} products')
        
        self.stdout.write(f'  ✓ Created {len(units)} inventory units')
        return units

    def _create_product_images(self, products):
        """Create product images with downloaded placeholder images - ensures ALL products have at least one image"""
        product_images = []
        if not REQUESTS_AVAILABLE:
            self.stdout.write('  ⚠️  Product images skipped (requests library not available)')
            return []
        
        # Create images for ALL products
        for idx, product in enumerate(products):
            # Create 1-3 images per product (at least 1)
            num_images = random.randint(1, 3)
            for img_num in range(num_images):
                try:
                    # Download placeholder image with unique seed
                    img_url = f"https://picsum.photos/800/600?random={product.id * 100 + img_num + idx * 1000}"
                    img_file = self._download_banner_image(img_url, f"product_{product.id}_{img_num+1}.jpg")
                    
                    if img_file:
                        product_image = ProductImage.objects.create(
                            product=product,
                            image=img_file,
                            is_primary=(img_num == 0),  # First image is primary
                            alt_text=f"{product.product_name} - Image {img_num+1}",
                            image_caption=f"High-quality image of {product.product_name}",
                            display_order=img_num
                        )
                        product_images.append(product_image)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Could not create image for product {product.id}: {e}'))
                    # Try alternative image source if first fails
                    try:
                        # Use a different placeholder service as fallback
                        alt_url = f"https://via.placeholder.com/800x600.jpg?text={product.product_name.replace(' ', '+')}"
                        img_file = self._download_banner_image(alt_url, f"product_{product.id}_{img_num+1}.jpg")
                        if img_file:
                            product_image = ProductImage.objects.create(
                                product=product,
                                image=img_file,
                                is_primary=(img_num == 0),
                                alt_text=f"{product.product_name} - Image {img_num+1}",
                                image_caption=f"Image of {product.product_name}",
                                display_order=img_num
                            )
                            product_images.append(product_image)
                    except:
                        continue
            
            # Progress update
            if (idx + 1) % 10 == 0:
                self.stdout.write(f'  ✓ Created images for {idx+1}/{len(products)} products...')
        
        if product_images:
            self.stdout.write(f'  ✓ Created {len(product_images)} product images for {len(products)} products')
        else:
            self.stdout.write('  ⚠️  No product images created')
        return product_images

    def _create_unit_images(self, units, colors):
        """Create unit images with downloaded placeholder images"""
        unit_images = []
        if not REQUESTS_AVAILABLE:
            self.stdout.write('  ⚠️  Unit images skipped (requests library not available)')
            return []
        
        # Create images for first 50 units (to have some with images)
        units_with_images = units[:min(50, len(units))]
        
        for idx, unit in enumerate(units_with_images):
            # Create 1-2 images per unit
            num_images = random.randint(1, 2)
            for img_num in range(num_images):
                try:
                    # Download placeholder image
                    img_url = f"https://picsum.photos/600/600?random={unit.id * 200 + img_num}"
                    img_file = self._download_banner_image(img_url, f"unit_{unit.id}_{img_num+1}.jpg")
                    
                    if img_file:
                        unit_image = InventoryUnitImage.objects.create(
                            inventory_unit=unit,
                            image=img_file,
                            is_primary=(img_num == 0),  # First image is primary
                            color=unit.product_color if unit.product_color else (random.choice(colors) if colors else None)
                        )
                        unit_images.append(unit_image)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Could not create image for unit {unit.id}: {e}'))
                    continue
        
        if unit_images:
            self.stdout.write(f'  ✓ Created {len(unit_images)} unit images')
        else:
            self.stdout.write('  ⚠️  No unit images created')
        return unit_images

    def _create_accessories(self, products):
        """Create product accessories relationships.
        Allows all product types to have accessories, including accessories having accessories.
        """
        accessories = []
        # All products can have accessories (including accessories themselves)
        all_products = [p for p in products if p.is_published]
        accessory_products = [p for p in products if p.product_type == 'AC' and p.is_published]
        
        if not all_products or not accessory_products:
            self.stdout.write(self.style.WARNING('  ⚠️  No accessories created: need both products and accessory products'))
            return accessories
        
        # Link accessories to products (up to 60% of all products, minimum 15)
        num_products_to_link = min(len(all_products), max(15, int(len(all_products) * 0.6)))
        products_to_link = random.sample(all_products, num_products_to_link)
        
        for main_product in products_to_link:
            # Select 1-5 accessories per product
            num_accessories = random.randint(1, min(5, len(accessory_products)))
            selected_accessories = random.sample(accessory_products, num_accessories)
            
            for accessory in selected_accessories:
                try:
                    # Skip if trying to link a product to itself
                    if main_product.id == accessory.id:
                        continue
                    
                    pa = ProductAccessory.objects.create(
                        main_product=main_product,
                        accessory=accessory,
                        required_quantity=random.randint(1, 2)
                    )
                    accessories.append(pa)
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  ⚠️  Could not link accessory {accessory.id} to product {main_product.id}: {e}'))
        
        self.stdout.write(f'  ✓ Created {len(accessories)} product accessory links')
        return accessories

    def _create_reviews(self, products, customers, count):
        """Create reviews"""
        reviews = []
        for i in range(count):
            product = random.choice(products)
            customer = random.choice(customers) if customers and random.choice([True, True, False]) else None
            
            # Increase video chance for carousel content (50% chance for first 20 reviews)
            has_video = random.choice([True, True, False]) if i < 20 else random.choice([True, False, False, False, False])
            
            review = Review.objects.create(
                customer=customer,
                product=product,
                rating=random.randint(1, 5),
                comment=random.choice([
                    "Great product! Very satisfied with my purchase.",
                    "Excellent quality and fast delivery. Highly recommend!",
                    "Good value for money. Works as expected.",
                    "Amazing features and great customer service.",
                    "Product arrived in perfect condition. Very happy!",
                    "Good quality but could be better. Still worth it.",
                    "Not bad, but expected more for the price.",
                    "Outstanding product! Exceeded my expectations.",
                ]),
                date_posted=timezone.now() - timedelta(days=random.randint(1, 180)),
                # Use various YouTube video IDs for variety
                video_url=f"https://www.youtube.com/watch?v=dQw4w9WgXcQ" if has_video else None,
            )
            reviews.append(review)
        
        self.stdout.write(f'  ✓ Created {len(reviews)} reviews')
        return reviews

    def _download_banner_image(self, url, filename):
        """Download an image from URL and return a File object"""
        if not REQUESTS_AVAILABLE:
            self.stdout.write(self.style.WARNING('  ⚠️  requests library not available. Install with: pip install requests'))
            return None
        
        try:
            response = requests.get(url, timeout=10, stream=True)
            response.raise_for_status()
            
            # Create a temporary file
            img_temp = NamedTemporaryFile(delete=False, suffix='.jpg')
            for chunk in response.iter_content(chunk_size=8192):
                img_temp.write(chunk)
            img_temp.flush()
            
            # Return a Django File object
            img_file = File(open(img_temp.name, 'rb'), name=filename)
            # Note: The temp file will be cleaned up after Django saves it
            return img_file
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Could not download banner image from {url}: {e}'))
            return None

    def _create_promotions(self, brands, promotion_types, products, admins, count):
        """Create promotions with banner images for carousel"""
        promotions = []
        marketing_managers = [a for a in admins if a.has_role(AdminRole.RoleChoices.MARKETING_MANAGER)]
        
        # First, create multiple promotions for each promotion type to ensure all types are well-represented
        # Create at least 2-3 promotions per type
        promotions_per_type = max(2, count // len(promotion_types) if promotion_types else 2)
        
        if promotion_types:
            for type_idx, promo_type in enumerate(promotion_types):
                # Create multiple promotions for this type
                for promo_idx in range(promotions_per_type):
                    brand = random.choice(brands)
                    
                    # Filter products by brand to ensure proper association
                    # Products can have brands via ManyToMany (p.brands) or single brand field
                    # Only use published products that exist
                    brand_products = [
                        p for p in products 
                        if p.is_published and (brand in p.brands.all() or (hasattr(p, 'brand') and p.brand == brand))
                    ]
                    if not brand_products:
                        # If no products for this brand, use any published products (fallback)
                        brand_products = [p for p in products if p.is_published]
                    if not brand_products:
                        # Last resort: use any products
                        brand_products = products
                    
                    # Different display locations for different types
                    if promo_type.code == 'FS':  # Flash Sale
                        display_locs = ['stories_carousel', 'flash_sales']
                        discount_pct = random.choice([30, 35, 40, 50])
                        discount_amt = None
                        duration_days = random.randint(1, 3)  # Short duration for flash sales
                        num_products = random.randint(3, 6)  # More products for flash sales
                    elif promo_type.code == 'SO':  # Special Offer
                        display_locs = ['stories_carousel', 'special_offers']
                        discount_pct = random.choice([15, 20, 25])
                        discount_amt = None
                        duration_days = random.randint(7, 14)
                        num_products = random.randint(2, 5)
                    elif promo_type.code == 'NA':  # New Arrival
                        display_locs = ['stories_carousel', 'special_offers']
                        discount_pct = random.choice([10, 15])
                        discount_amt = None
                        duration_days = random.randint(14, 30)
                        num_products = random.randint(2, 4)  # Fewer products for new arrivals
                    elif promo_type.code == 'WD':  # Weekend Deal
                        display_locs = ['special_offers', 'flash_sales']
                        discount_pct = random.choice([20, 25, 30])
                        discount_amt = None
                        duration_days = random.randint(2, 4)  # Weekend only
                        num_products = random.randint(3, 6)
                    elif promo_type.code == 'BD':  # Bundle Deal
                        display_locs = ['special_offers']
                        discount_pct = None
                        discount_amt = random.randint(10000, 25000)  # Fixed amount for bundles
                        duration_days = random.randint(7, 21)
                        num_products = random.randint(4, 8)  # More products for bundles
                    elif promo_type.code == 'CL':  # Clearance Sale
                        display_locs = ['special_offers', 'flash_sales']
                        discount_pct = random.choice([40, 50, 60])  # Higher discounts for clearance
                        discount_amt = None
                        duration_days = random.randint(14, 30)
                        num_products = random.randint(5, 10)  # Many products for clearance
                    else:
                        display_locs = random.sample(['stories_carousel', 'special_offers', 'flash_sales'], random.randint(1, 3))
                        discount_pct = random.choice([10, 15, 20, 25, 30]) if random.choice([True, False]) else None
                        discount_amt = random.randint(5000, 20000) if random.choice([True, False]) else None
                        duration_days = random.randint(7, 30)
                        num_products = random.randint(2, 5)
                    
                    start_date = timezone.now() - timedelta(days=random.randint(0, 5))
                    end_date = start_date + timedelta(days=duration_days)
                    
                    # Download banner image for stories_carousel
                    banner_image_file = None
                    if 'stories_carousel' in display_locs:
                        banner_url = f"https://picsum.photos/1200/600?random={type_idx*1000 + promo_idx*100 + 1000}"
                        banner_image_file = self._download_banner_image(banner_url, f"promo_{promo_type.code.lower()}_{type_idx+1}_{promo_idx+1}.jpg")
                    
                    # Create type-specific titles with variations
                    title_templates = {
                        'FS': [
                            f"⚡ Flash Sale - {random.choice(['Today Only', 'Limited Time', 'Hurry Up'])}",
                            f"⚡ Mega Flash Sale - {random.choice(['24 Hours Only', 'Ends Tonight', 'Last Chance'])}",
                            f"⚡ Super Flash Sale - {random.choice(['Don\'t Miss Out', 'Limited Stock', 'Act Fast'])}",
                        ],
                        'SO': [
                            f"✨ Special Offer - {random.choice(['Exclusive Deal', 'Best Price', 'Limited Stock'])}",
                            f"✨ Exclusive Special - {random.choice(['Premium Deal', 'VIP Offer', 'Special Price'])}",
                            f"✨ Limited Special - {random.choice(['One-Time Deal', 'Exclusive Price', 'Special Discount'])}",
                        ],
                        'NA': [
                            f"🆕 New Arrival - {random.choice(['Just In', 'Latest Models', 'Fresh Stock'])}",
                            f"🆕 Latest Arrival - {random.choice(['Brand New', 'Just Launched', 'New Collection'])}",
                            f"🆕 Fresh Arrival - {random.choice(['Newly Added', 'Latest Release', 'New Products'])}",
                        ],
                        'WD': [
                            f"🎉 Weekend Deal - {random.choice(['Weekend Special', 'Saturday Sale', 'Sunday Savings'])}",
                            f"🎉 Weekend Special - {random.choice(['Friday Flash', 'Saturday Super Sale', 'Sunday Deal'])}",
                            f"🎉 Weekend Exclusive - {random.choice(['Weekend Only', 'Saturday Special', 'Sunday Offer'])}",
                        ],
                        'BD': [
                            f"📦 Bundle Deal - {random.choice(['Buy More Save More', 'Combo Offer', 'Package Deal'])}",
                            f"📦 Mega Bundle - {random.choice(['Complete Package', 'Full Set Deal', 'Bundle Special'])}",
                            f"📦 Bundle Special - {random.choice(['Combo Pack', 'Set Deal', 'Package Offer'])}",
                        ],
                        'CL': [
                            f"🏷️ Clearance Sale - {random.choice(['Final Clearance', 'Last Chance', 'Stock Clearance'])}",
                            f"🏷️ Mega Clearance - {random.choice(['Final Sale', 'Last Stock', 'Clearance Event'])}",
                            f"🏷️ Clearance Special - {random.choice(['End of Season', 'Final Reduction', 'Clearance Now'])}",
                        ],
                    }
                    
                    # Select title variation based on promo_idx
                    title_list = title_templates.get(promo_type.code, [f"{promo_type.name} - Special Deal"])
                    title = title_list[promo_idx % len(title_list)]
                    
                    # Vary the brand for each promotion of the same type
                    if promo_idx > 0:
                        brand = random.choice(brands)
                        # Re-filter products for the new brand
                        brand_products = [
                            p for p in products 
                            if p.is_published and (brand in p.brands.all() or (hasattr(p, 'brand') and p.brand == brand))
                        ]
                        if not brand_products:
                            brand_products = [p for p in products if p.is_published]
                        if not brand_products:
                            brand_products = products
                    
                promotion = Promotion.objects.create(
                    brand=brand,
                    promotion_type=promo_type,
                        title=title,
                        description=f"Don't miss this amazing {promo_type.name.lower()}! {random.choice(['Limited time only!', 'While supplies last!', 'Act now!', 'Best prices guaranteed!', 'Shop now and save!'])}",
                    discount_percentage=discount_pct,
                    discount_amount=discount_amt,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True,  # All type examples should be active
                    display_locations=display_locs,
                        product_types=random.choice(['PH', 'LT', 'TB', 'AC', '']) if random.choice([True, False]) else '',
                    created_by=random.choice(marketing_managers) if marketing_managers else None,
                    banner_image=banner_image_file if banner_image_file else None
                )
                
                # Associate products with promotion (filtered by brand)
                if brand_products:
                    selected_products = random.sample(brand_products, min(num_products, len(brand_products)))
                    # Ensure all selected products actually exist in the database
                    existing_product_ids = [p.id for p in selected_products if Product.objects.filter(id=p.id).exists()]
                    if existing_product_ids:
                        promotion.products.set(existing_product_ids)
                        self.stdout.write(f'    → Created {promo_type.name} promotion #{promo_idx+1} with {len(existing_product_ids)} products (brand: {brand.name})')
                    else:
                        self.stdout.write(self.style.WARNING(f'    ⚠️  No valid products found for {promo_type.name} promotion #{promo_idx+1}'))
                else:
                    self.stdout.write(self.style.WARNING(f'    ⚠️  No products available for brand {brand.name}'))
                
                promotions.append(promotion)
        
        # Create additional random promotions to reach the requested count
        remaining_count = max(0, count - len(promotions))
        for i in range(remaining_count):
            brand = random.choice(brands)
            promo_type = random.choice(promotion_types) if promotion_types else None
            
            # Filter products by brand to ensure proper association
            # Only use published products that exist
            brand_products = [
                p for p in products 
                if p.is_published and (brand in p.brands.all() or (hasattr(p, 'brand') and p.brand == brand))
            ]
            if not brand_products:
                # If no products for this brand, use any published products (fallback)
                brand_products = [p for p in products if p.is_published]
            if not brand_products:
                # Last resort: use any products
                brand_products = products
            
            start_date = timezone.now() - timedelta(days=random.randint(0, 30))
            end_date = start_date + timedelta(days=random.randint(7, 30))
            
            # Ensure at least some additional promotions appear in stories carousel
            display_locs = random.sample(['stories_carousel', 'special_offers', 'flash_sales'], random.randint(1, 3))
            if i < 3 and 'stories_carousel' not in display_locs:
                display_locs.append('stories_carousel')
            
            # For promotions with stories_carousel, download banner images
            banner_image_file = None
            has_stories_carousel = 'stories_carousel' in display_locs
            if has_stories_carousel:
                # Download placeholder banner image
                banner_url = f"https://picsum.photos/1200/600?random={len(promotions)+i+2000}"
                banner_image_file = self._download_banner_image(banner_url, f"promo_banner_{len(promotions)+i+1}.jpg")
            
            promotion = Promotion.objects.create(
                brand=brand,
                promotion_type=promo_type,
                title=f"{promo_type.name if promo_type else 'Special'} - {random.choice(['Weekend', 'Flash', 'Summer', 'Holiday'])} Sale",
                description=f"Amazing {promo_type.name.lower() if promo_type else 'special'} offer! Don't miss out!",
                discount_percentage=random.choice([10, 15, 20, 25, 30]) if random.choice([True, False]) else None,
                discount_amount=random.randint(5000, 20000) if random.choice([True, False]) else None,
                start_date=start_date,
                end_date=end_date,
                is_active=random.choice([True, True, False]),
                display_locations=display_locs,
                product_types=random.choice(['PH', 'LT', 'TB', '']) if random.choice([True, False]) else '',
                created_by=random.choice(marketing_managers) if marketing_managers else None,
                banner_image=banner_image_file if banner_image_file else None
            )
            
            # Associate products with promotion (filtered by brand)
            if brand_products:
                num_products = random.randint(2, 6)
                selected_products = random.sample(brand_products, min(num_products, len(brand_products)))
                # Ensure all selected products actually exist in the database
                existing_product_ids = [p.id for p in selected_products if Product.objects.filter(id=p.id).exists()]
                if existing_product_ids:
                    promotion.products.set(existing_product_ids)
                else:
                    self.stdout.write(self.style.WARNING(f'    ⚠️  No valid products found for promotion'))
            else:
                self.stdout.write(self.style.WARNING(f'    ⚠️  No products available for brand {brand.name}'))
            
            promotions.append(promotion)
        
        # Verify all promotions have products associated
        promotions_with_products = 0
        total_products_linked = 0
        for promo in promotions:
            product_count = promo.products.count()
            if product_count > 0:
                promotions_with_products += 1
                total_products_linked += product_count
        
        self.stdout.write(f'  ✓ Created {len(promotions)} promotions (ensuring all {len(promotion_types) if promotion_types else 0} types are represented)')
        self.stdout.write(f'  ✓ {promotions_with_products}/{len(promotions)} promotions have products associated ({total_products_linked} total product links)')
        
        if promotions_with_products < len(promotions):
            self.stdout.write(self.style.WARNING(f'  ⚠️  {len(promotions) - promotions_with_products} promotions have no products associated'))
        
        return promotions

    def _create_reservation_requests(self, admins, units, count):
        """Create reservation requests"""
        salespersons = [a for a in admins if a.has_role(AdminRole.RoleChoices.SALESPERSON)]
        inventory_managers = [a for a in admins if a.has_role(AdminRole.RoleChoices.INVENTORY_MANAGER)]
        available_units = [u for u in units if u.sale_status == 'AV']
        
        if not salespersons or not available_units:
            return []
        
        requests = []
        for i in range(count):
            salesperson = random.choice(salespersons)
            units_to_reserve = random.sample(available_units, min(random.randint(1, 3), len(available_units)))
            
            status = random.choice(['PE', 'AP', 'RE', 'EX', 'RT'])
            approved_by = None
            approved_at = None
            
            if status == 'AP':
                approved_by = random.choice(inventory_managers) if inventory_managers else None
                approved_at = timezone.now() - timedelta(days=random.randint(1, 30))
            
            request = ReservationRequest.objects.create(
                requesting_salesperson=salesperson,
                status=status,
                approved_by=approved_by,
                approved_at=approved_at,
                expires_at=approved_at + timedelta(days=2) if approved_at else None,
                notes=f"Reservation request #{i+1} - {random.choice(['Urgent', 'Standard', 'Customer request'])}"
            )
            
            request.inventory_units.set(units_to_reserve)
            
            if status == 'AP':
                for unit in units_to_reserve:
                    unit.sale_status = 'RS'
                    unit.reserved_by = salesperson
                    unit.reserved_until = approved_at + timedelta(days=2) if approved_at else None
                    unit.save()
            
            requests.append(request)
        
        self.stdout.write(f'  ✓ Created {len(requests)} reservation requests')
        return requests

    def _create_return_requests(self, admins, units, count):
        """Create return requests"""
        salespersons = [a for a in admins if a.has_role(AdminRole.RoleChoices.SALESPERSON)]
        inventory_managers = [a for a in admins if a.has_role(AdminRole.RoleChoices.INVENTORY_MANAGER)]
        reserved_units = [u for u in units if u.sale_status == 'RS']
        
        if not salespersons or not reserved_units:
            return []
        
        requests = []
        for i in range(count):
            salesperson = random.choice(salespersons)
            units_to_return = random.sample(reserved_units, min(random.randint(1, 3), len(reserved_units)))
            
            status = random.choice(['PE', 'AP', 'RE'])
            approved_by = None
            approved_at = None
            
            if status == 'AP':
                approved_by = random.choice(inventory_managers) if inventory_managers else None
                approved_at = timezone.now() - timedelta(days=random.randint(1, 7))
            
            request = ReturnRequest.objects.create(
                requesting_salesperson=salesperson,
                status=status,
                approved_by=approved_by,
                approved_at=approved_at,
                notes=f"Return request #{i+1} - {random.choice(['Customer cancelled', 'Wrong item', 'Defective unit'])}"
            )
            
            request.inventory_units.set(units_to_return)
            requests.append(request)
        
        self.stdout.write(f'  ✓ Created {len(requests)} return requests')
        return requests

    def _create_unit_transfers(self, admins, units, count):
        """Create unit transfers"""
        salespersons = [a for a in admins if a.has_role(AdminRole.RoleChoices.SALESPERSON)]
        inventory_managers = [a for a in admins if a.has_role(AdminRole.RoleChoices.INVENTORY_MANAGER)]
        reserved_units = [u for u in units if u.sale_status == 'RS']
        
        if len(salespersons) < 2 or not reserved_units:
            return []
        
        transfers = []
        for i in range(count):
            from_salesperson = random.choice(salespersons)
            to_salesperson = random.choice([s for s in salespersons if s != from_salesperson])
            unit = random.choice(reserved_units)
            
            status = random.choice(['PE', 'AP', 'RE'])
            approved_by = None
            approved_at = None
            
            if status == 'AP':
                approved_by = random.choice(inventory_managers) if inventory_managers else None
                approved_at = timezone.now() - timedelta(days=random.randint(1, 7))
            
            transfer = UnitTransfer.objects.create(
                inventory_unit=unit,
                from_salesperson=from_salesperson,
                to_salesperson=to_salesperson,
                status=status,
                requested_at=timezone.now() - timedelta(days=random.randint(1, 14)),
                approved_at=approved_at,
                approved_by=approved_by,
                notes=f"Transfer request #{i+1}"
            )
            
            transfers.append(transfer)
        
        self.stdout.write(f'  ✓ Created {len(transfers)} unit transfers')
        return transfers

    def _create_orders(self, customers, brands, units, count):
        """Create orders"""
        orders = []
        available_units = [u for u in units if u.sale_status in ['AV', 'RS']]
        
        for i in range(count):
            customer = random.choice(customers)
            brand = random.choice(brands)
            status = random.choice(['Pending', 'Paid', 'Delivered', 'Canceled'])
            order_source = random.choice(['WALK_IN', 'ONLINE'])
            
            order = Order.objects.create(
                customer=customer,
                user=customer.user if customer.user else None,
                brand=brand,
                order_source=order_source,
                status=status,
                total_amount=Decimal('0.00'),
                created_at=timezone.now() - timedelta(days=random.randint(1, 90))
            )
            
            # Create order items
            selected_units = random.sample(available_units, min(random.randint(1, 3), len(available_units)))
            total = Decimal('0.00')
            
            for unit in selected_units:
                quantity = 1 if unit.product_template.product_type != 'AC' else random.randint(1, 3)
                unit_price = unit.selling_price
                OrderItem.objects.create(
                    order=order,
                    inventory_unit=unit,
                    quantity=quantity,
                    unit_price_at_purchase=unit_price
                )
                total += unit_price * quantity
                
                if status in ['Paid', 'Delivered']:
                    unit.sale_status = 'SD'
                    unit.save()
            
            order.total_amount = total
            order.save()
            orders.append(order)
        
        self.stdout.write(f'  ✓ Created {len(orders)} orders')
        return orders

    def _create_leads(self, customers, brands, units, admins, count):
        """Create leads"""
        leads = []
        available_units = [u for u in units if u.sale_status == 'AV']
        salespersons = [a for a in admins if a.has_role(AdminRole.RoleChoices.SALESPERSON)]
        
        for i in range(count):
            brand = random.choice(brands)
            customer = random.choice(customers) if random.choice([True, False]) else None
            status = random.choice(['NEW', 'CONTACTED', 'CONVERTED', 'CLOSED', 'EXPIRED'])
            
            lead = Lead.objects.create(
                customer_name=customer.name if customer else f"Customer {i+1}",
                customer_phone=customer.phone if customer else f"+2547{random.randint(10000000, 99999999)}",
                customer_email=customer.email if customer else f"customer{i+1}@example.com",
                delivery_address=f"{random.randint(100, 999)} Main Street, Nairobi",
                customer=customer,
                brand=brand,
                status=status,
                assigned_salesperson=random.choice(salespersons) if salespersons and random.choice([True, False]) else None,
                contacted_at=timezone.now() - timedelta(days=random.randint(1, 30)) if status in ['CONTACTED', 'CONVERTED'] else None,
                converted_at=timezone.now() - timedelta(days=random.randint(1, 20)) if status == 'CONVERTED' else None,
                total_value=Decimal('0.00'),
                submitted_at=timezone.now() - timedelta(days=random.randint(1, 60))
            )
            
            # Create lead items
            selected_units = random.sample(available_units, min(random.randint(1, 3), len(available_units)))
            total = Decimal('0.00')
            
            for unit in selected_units:
                quantity = 1 if unit.product_template.product_type != 'AC' else random.randint(1, 3)
                unit_price = unit.selling_price
                LeadItem.objects.create(
                    lead=lead,
                    inventory_unit=unit,
                    quantity=quantity,
                    unit_price=unit_price
                )
                total += unit_price * quantity
            
            lead.total_value = total
            lead.save()
            leads.append(lead)
        
        self.stdout.write(f'  ✓ Created {len(leads)} leads')
        return leads

    def _create_carts(self, customers, brands, units, promotions, count):
        """Create carts"""
        carts = []
        available_units = [u for u in units if u.sale_status == 'AV']
        
        for i in range(count):
            brand = random.choice(brands)
            customer = random.choice(customers) if random.choice([True, False]) else None
            is_submitted = random.choice([True, False, False])
            
            cart = Cart.objects.create(
                session_key=f"session_{uuid.uuid4().hex[:20]}" if not customer else '',
                customer=customer,
                brand=brand,
                customer_name=customer.name if customer else f"Guest {i+1}",
                customer_phone=customer.phone if customer else f"+2547{random.randint(10000000, 99999999)}",
                customer_email=customer.email if customer else f"guest{i+1}@example.com",
                delivery_address=f"{random.randint(100, 999)} Main Street, Nairobi",
                is_submitted=is_submitted,
                created_at=timezone.now() - timedelta(hours=random.randint(1, 48)),
                expires_at=timezone.now() + timedelta(hours=random.randint(1, 24))
            )
            
            # Create cart items
            selected_units = random.sample(available_units, min(random.randint(1, 3), len(available_units)))
            
            for unit in selected_units:
                quantity = 1 if unit.product_template.product_type != 'AC' else random.randint(1, 3)
                promotion = random.choice(promotions) if promotions and random.choice([True, False]) else None
                unit_price = unit.selling_price
                
                CartItem.objects.create(
                    cart=cart,
                    inventory_unit=unit,
                    quantity=quantity,
                    unit_price=unit_price,
                    promotion=promotion
                )
            
            carts.append(cart)
        
        self.stdout.write(f'  ✓ Created {len(carts)} carts')
        return carts

    def _create_notifications(self, admins, customers, reservations, returns, transfers, count):
        """Create notifications"""
        notifications = []
        all_users = list(User.objects.filter(admin__isnull=False)) + list(User.objects.filter(customer__isnull=False))
        
        notification_types = [
            'RA', 'RR', 'RE', 'TA', 'TR', 'FA', 'FR', 'OC', 'UR', 'RP', 'NL'
        ]
        
        for i in range(count):
            recipient = random.choice(all_users)
            notification_type = random.choice(notification_types)
            
            titles = {
                'RA': 'Reservation Approved',
                'RR': 'Reservation Rejected',
                'RE': 'Reservation Expired',
                'TA': 'Return Approved',
                'TR': 'Return Rejected',
                'FA': 'Transfer Approved',
                'FR': 'Transfer Rejected',
                'OC': 'Order Created',
                'UR': 'Unit Reserved',
                'RP': 'Request Pending Approval',
                'NL': 'New Lead',
            }
            
            notification = Notification.objects.create(
                recipient=recipient,
                notification_type=notification_type,
                title=titles.get(notification_type, 'Notification'),
                message=f"This is a {titles.get(notification_type, 'notification')} message.",
                is_read=random.choice([True, False, False]),
                created_at=timezone.now() - timedelta(days=random.randint(0, 30))
            )
            notifications.append(notification)
        
        self.stdout.write(f'  ✓ Created {len(notifications)} notifications')
        return notifications

    def _create_audit_logs(self, admins, customers, count):
        """Create audit logs"""
        logs = []
        all_users = list(User.objects.filter(admin__isnull=False)) + list(User.objects.filter(customer__isnull=False))
        action_types = ['CR', 'UP', 'DL', 'AP', 'RJ', 'RS', 'RL', 'TR']
        model_names = ['Product', 'InventoryUnit', 'Order', 'ReservationRequest', 'ReturnRequest']
        
        for i in range(count):
            user = random.choice(all_users) if all_users else None
            action = random.choice(action_types)
            model_name = random.choice(model_names)
            object_id = random.randint(1, 1000)
            
            log = AuditLog.objects.create(
                user=user,
                action=action,
                model_name=model_name,
                object_id=object_id,
                object_repr=f"{model_name} #{object_id}",
                old_value={'field': 'old_value'} if action == 'UP' else None,
                new_value={'field': 'new_value'} if action in ['CR', 'UP'] else None,
                ip_address=f"192.168.1.{random.randint(1, 255)}",
                user_agent=f"Mozilla/5.0 (dummy user agent {i})",
                timestamp=timezone.now() - timedelta(days=random.randint(0, 90))
            )
            logs.append(log)
        
        self.stdout.write(f'  ✓ Created {len(logs)} audit logs')
        return logs

    def _print_summary(self):
        """Print summary of created data"""
        self.stdout.write(self.style.SUCCESS('\n📊 Data Summary:'))
        self.stdout.write(f'  👥 Users: {User.objects.count()}')
        self.stdout.write(f'  👨‍💼 Admins: {Admin.objects.count()}')
        self.stdout.write(f'  👤 Customers: {Customer.objects.count()}')
        self.stdout.write(f'  🏷️  Brands: {Brand.objects.count()}')
        self.stdout.write(f'  🎨 Colors: {Color.objects.count()}')
        self.stdout.write(f'  🏷️  Tags: {Tag.objects.count()}')
        self.stdout.write(f'  📦 Products: {Product.objects.count()}')
        self.stdout.write(f'  📸 Product Images: {ProductImage.objects.count()}')
        self.stdout.write(f'  📱 Inventory Units: {InventoryUnit.objects.count()}')
        self.stdout.write(f'  🖼️  Unit Images: {InventoryUnitImage.objects.count()}')
        self.stdout.write(f'  🔗 Product Accessories: {ProductAccessory.objects.count()}')
        self.stdout.write(f'  ⭐ Reviews: {Review.objects.count()}')
        self.stdout.write(f'  🎁 Promotions: {Promotion.objects.count()}')
        self.stdout.write(f'  📋 Reservation Requests: {ReservationRequest.objects.count()}')
        self.stdout.write(f'  ↩️  Return Requests: {ReturnRequest.objects.count()}')
        self.stdout.write(f'  🔄 Unit Transfers: {UnitTransfer.objects.count()}')
        self.stdout.write(f'  🛒 Orders: {Order.objects.count()}')
        self.stdout.write(f'  📦 Order Items: {OrderItem.objects.count()}')
        self.stdout.write(f'  📞 Leads: {Lead.objects.count()}')
        self.stdout.write(f'  📋 Lead Items: {LeadItem.objects.count()}')
        self.stdout.write(f'  🛍️  Carts: {Cart.objects.count()}')
        self.stdout.write(f'  🛒 Cart Items: {CartItem.objects.count()}')
        self.stdout.write(f'  🔔 Notifications: {Notification.objects.count()}')
        self.stdout.write(f'  📝 Audit Logs: {AuditLog.objects.count()}')
        self.stdout.write(f'  📍 Acquisition Sources: {UnitAcquisitionSource.objects.count()}')

