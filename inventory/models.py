from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import AbstractUser
from django.conf import settings 
from decimal import Decimal
import uuid
from django.utils import timezone
from datetime import timedelta
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


# -------------------------------------------------------------------------
# 1. AUTHENTICATION MODELS (Core User Structure)
# -------------------------------------------------------------------------

class User(AbstractUser):
    """Custom User model extending AbstractUser to differentiate between Admin and Customer roles."""
    # Custom methods for role checking (assumes Admin/Customer models exist)
    @property
    def is_admin(self):
        if hasattr(self, 'admin'):
            return True
        return False

    @property
    def is_customer(self):
        if hasattr(self, 'customer'):
            return True
        return False

class AdminRole(models.Model):
    """Model representing admin roles in the system."""
    class RoleChoices(models.TextChoices):
        SALESPERSON = 'SP', _('Salesperson')
        INVENTORY_MANAGER = 'IM', _('Inventory Manager')
        CONTENT_CREATOR = 'CC', _('Content Creator')
        ORDER_MANAGER = 'OM', _('Order Manager')
        MARKETING_MANAGER = 'MM', _('Marketing Manager')
    
    name = models.CharField(max_length=2, choices=RoleChoices.choices, unique=True, db_column='role_code')
    display_name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Admin Role"
        verbose_name_plural = "Admin Roles"
        ordering = ['display_name']
    
    def __str__(self):
        return self.get_name_display()
    
    @property
    def role_code(self):
        """Backward compatibility property."""
        return self.name

class Admin(models.Model):
    """Model representing an Admin user with elevated privileges."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    admin_code = models.CharField(max_length=20, unique=True)
    roles = models.ManyToManyField(AdminRole, related_name='admins', blank=True)
    
    # Brand assignment
    brands = models.ManyToManyField(
        'Brand',
        related_name='admins',
        blank=True,
        help_text="Brands this admin can access"
    )
    is_global_admin = models.BooleanField(
        default=False,
        help_text="If True, admin can access all brands"
    )

    def __str__(self):
        return self.user.username if self.user else f"Admin {self.admin_code}"
    
    def has_role(self, role_code):
        """Check if admin has a specific role."""
        return self.roles.filter(name=role_code).exists()
    
    @property
    def is_salesperson(self):
        return self.has_role(AdminRole.RoleChoices.SALESPERSON)
    
    @property
    def is_inventory_manager(self):
        return self.has_role(AdminRole.RoleChoices.INVENTORY_MANAGER)
    
    @property
    def is_content_creator(self):
        return self.has_role(AdminRole.RoleChoices.CONTENT_CREATOR)
    
    @property
    def is_order_manager(self):
        return self.has_role(AdminRole.RoleChoices.ORDER_MANAGER)
    
    @property
    def is_marketing_manager(self):
        return self.has_role(AdminRole.RoleChoices.MARKETING_MANAGER)
    
class Customer(models.Model):
    """Model representing a Customer user (global, no brand field)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    
    # Contact information
    name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, db_index=True, blank=True)  # For customer recognition
    phone_number = models.CharField(max_length=15, blank=True)  # Keep for backward compatibility
    email = models.EmailField(blank=True, null=True)  # Optional
    address = models.TextField(blank=True, default='')  # Keep for backward compatibility
    delivery_address = models.TextField(blank=True)  # Simple text field for delivery
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)  # Allow null for existing records
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)  # Allow null for existing records
    last_lead_at = models.DateTimeField(null=True, blank=True)  # Last lead submission
    total_orders = models.IntegerField(default=0)  # Total orders count
    
    class Meta:
        indexes = [
            models.Index(fields=['phone']),  # For customer recognition
        ]
    
    def __str__(self):
        if self.user:
            return self.user.username
        return f"{self.name or 'Unknown'} ({self.phone or 'No phone'})"


# -------------------------------------------------------------------------
# 2. BRAND MODEL
# -------------------------------------------------------------------------

class Brand(models.Model):
    """Represents a brand name (customer-facing identity)."""
    code = models.CharField(max_length=20, unique=True, db_index=True)  # e.g., "BRAND_A", "BRAND_B"
    name = models.CharField(max_length=100)  # Display name
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Brand identity
    logo = models.ImageField(upload_to='brands/logos/', blank=True, null=True)
    primary_color = models.CharField(max_length=7, blank=True, help_text="Hex color code")
    
    # E-commerce settings
    ecommerce_domain = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Domain for this brand's e-commerce site"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"


# -------------------------------------------------------------------------
# 3. UTILITY & PRODUCT TEMPLATE MODELS
# -------------------------------------------------------------------------

class Color(models.Model):
    """Model representing a color option for products."""
    name = models.CharField(max_length=50, unique=True)
    hex_code = models.CharField(max_length=7, unique=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    """
    Product TEMPLATE (generic model description, e.g., "iPhone 15 Pro").
    This stores descriptive, non-inventory-specific details.
    """
    class ProductType(models.TextChoices):
        PHONE = 'PH', _('Phone')
        LAPTOP = 'LT', _('Laptop')
        TABLET = 'TB', _('Tablet/iPad')
        ACCESSORY = 'AC', _('Accessory')

    product_type = models.CharField(max_length=2, choices=ProductType.choices, default=ProductType.ACCESSORY)
    product_name = models.CharField(max_length=255, verbose_name="Product Name", db_index=True)
    product_description = models.TextField(blank=True)
    
    # Generic product details (used for conditional validation in InventoryUnit)
    brand = models.CharField(max_length=50, help_text="e.g., Samsung, Apple, Dell",default='N/A')
    model_series = models.CharField(max_length=100, help_text="e.g., S series, Fold, XPS",default='N/A')

    # Relationships
    related_accessories = models.ManyToManyField(
        'self', through='ProductAccessory', symmetrical=False,
        related_name='parent_products', blank=True
    )
    
    # Inventory Management Fields
    min_stock_threshold = models.IntegerField(
        null=True, blank=True,
        help_text="Minimum stock level before triggering low stock alert"
    )
    reorder_point = models.IntegerField(
        null=True, blank=True,
        help_text="Stock level at which to reorder/restock"
    )
    is_discontinued = models.BooleanField(
        default=False,
        help_text="Mark product as discontinued (no longer in catalog)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='products_created', null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='products_updated', null=True, blank=True)
    
    # SEO Fields
    meta_title = models.CharField(max_length=60, blank=True, help_text="SEO title (50-60 chars recommended)")
    meta_description = models.TextField(max_length=160, blank=True, help_text="SEO description (150-160 chars recommended)")
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True, help_text="URL-friendly slug (auto-generated from product_name if not provided)")
    og_image = models.ImageField(upload_to='og_images/%Y/%m/', blank=True, null=True, help_text="Social sharing image (Open Graph)")
    keywords = models.CharField(max_length=255, blank=True, help_text="Comma-separated keywords for SEO")
    
    # Content Fields
    product_highlights = models.JSONField(default=list, blank=True, help_text="List of key features/highlights (bullet points)")
    long_description = models.TextField(blank=True, help_text="Extended product description for detailed content")
    is_published = models.BooleanField(default=True, help_text="Whether product is published (visible on e-commerce site)")
    
    # Product Video
    product_video_url = models.URLField(max_length=500, blank=True, null=True, help_text="Link to product video (YouTube, Vimeo, etc.)")
    product_video_file = models.FileField(upload_to='product_videos/%Y/%m/', blank=True, null=True, help_text="Upload product video file")
    
    # Tags (Many-to-Many relationship)
    tags = models.ManyToManyField('Tag', related_name='products', blank=True, help_text="Tags for organizing and categorizing products")
    
    # Brand assignment
    brands = models.ManyToManyField(
        'Brand',
        related_name='products',
        blank=True,
        help_text="Brands this product is available for. Empty = all brands."
    )
    is_global = models.BooleanField(
        default=False,
        help_text="If True, product is available to all brands regardless of brand assignment"
    )

    def __str__(self):
        return self.product_name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug from product_name if not provided"""
        if not self.slug and self.product_name:
            from django.utils.text import slugify
            base_slug = slugify(self.product_name)
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
    

class ProductImage(models.Model):
    """Stores one image file linked to a Product."""
    # This creates the one-to-many link. 'related_name' allows us to access all
    # images for a product using product.images.all()
    product = models.ForeignKey(
        Product, 
        related_name='images', 
        on_delete=models.CASCADE
    )
    # Use ImageField or FileField for storing the file upload path
    image = models.ImageField(upload_to='product_photos/%Y/%m/')
    # Optional: Flag one image as the primary/display image
    is_primary = models.BooleanField(default=False)
    
    # SEO and Content Fields
    alt_text = models.CharField(max_length=255, blank=True, help_text="Required for SEO and accessibility")
    image_caption = models.CharField(max_length=255, blank=True, help_text="Optional caption for the image")
    display_order = models.IntegerField(default=0, help_text="Order in which images should be displayed (lower numbers first)")

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"Image for {self.product.product_name} (ID: {self.id})"

class ProductAccessory(models.Model):
    """Links a product TEMPLATE to an Accessory TEMPLATE.
    Allows all product types (phones, laptops, tablets, and accessories) to have accessories.
    """
    main_product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='product_accessories',
        verbose_name="Product Template"
    )
    accessory = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='used_by_products',
        verbose_name="Accessory Item Template"
    )
    required_quantity = models.PositiveIntegerField(default=1)
    class Meta:
        unique_together = ('main_product', 'accessory')
    def __str__(self):
        return f"{self.accessory.product_name} for {self.main_product.product_name}"


class Tag(models.Model):
    """Tags for organizing and categorizing products."""
    name = models.CharField(max_length=50, unique=True, help_text="Tag name (e.g., 'premium', 'bestseller', 'new')")
    slug = models.SlugField(max_length=50, unique=True, db_index=True, help_text="URL-friendly slug")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Auto-generate slug from name if not provided"""
        if not self.slug and self.name:
            from django.utils.text import slugify
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


# -------------------------------------------------------------------------
# 3. INVENTORY TRACKING MODELS
# -------------------------------------------------------------------------

class UnitAcquisitionSource(models.Model):
    """
    Tracks contact details for external suppliers and import partners.
    Used when InventoryUnit.source is 'SU' or 'IM'.
    """
    class SourceType(models.TextChoices):
        SUPPLIER = 'SU', _('Supplier')
        IMPORT_PARTNER = 'IM', _('Import Partner')

    source_type = models.CharField(max_length=2, choices=SourceType.choices)
    name = models.CharField(max_length=255, help_text="Name of the company or contact person.")
    phone_number = models.CharField(max_length=20, blank=True)

    class Meta:
        verbose_name_plural = "Unit Acquisition Sources"

    def __str__(self):
        return f"{self.get_source_type_display()}: {self.name}"

class InventoryUnit(models.Model):
    """
    Model representing physical units in stock.
    - Phones/Laptops/Tablets: Unique units identified by serial_number/IMEI. Quantity always 1.
    - Accessories: Bulk items without unique identifiers. Quantity required and can be > 1.
    """
    class ConditionChoices(models.TextChoices):
        NEW = 'N', _('New')
        REFURBISHED = 'R', _('Refurbished')
        PRE_OWNED = 'P', _('Pre-owned')
        DEFECTIVE = 'D', _('Defective') # Used for buybacks on defective units

    class SourceChoices(models.TextChoices):
        BUYBACK_CUSTOMER = 'BB', _('Buyback (Customer)')
        EXTERNAL_SUPPLIER = 'SU', _('External Supplier')
        EXTERNAL_IMPORT = 'IM', _('External Import')

    class GradeChoices(models.TextChoices):
        GRADE_A = 'A', _('Grade A')
        GRADE_B = 'B', _('Grade B')

    class SaleStatusChoices(models.TextChoices):
        AVAILABLE = 'AV', _('Available')
        SOLD = 'SD', _('Sold')
        RESERVED = 'RS', _('Reserved')
        RETURNED = 'RT', _('Returned')
        PENDING_PAYMENT = 'PP', _('Pending Payment')

    # --- Relationships ---
    product_template = models.ForeignKey(
        Product, on_delete=models.PROTECT, related_name='inventory_units', 
        verbose_name="Product Model/Template"
    )
    product_color = models.ForeignKey(Color, on_delete=models.PROTECT, null=True, blank=True)
    
    # Conditional link to external contact details
    acquisition_source_details = models.ForeignKey(
        UnitAcquisitionSource, on_delete=models.SET_NULL, null=True, blank=True,
        help_text="Details for Supplier or Import source (if applicable)"
    )

    # --- QUANTITY FIELD (Conditional use) ---
    quantity = models.PositiveIntegerField(
        default=1, 
        help_text="Quantity: 1 for Phones/Laptops/Tablets (unique units). Required and can be > 1 for Accessories (no unique identifier)."
    )

    # --- Status & Pricing ---
    condition = models.CharField(max_length=1, choices=ConditionChoices.choices, default=ConditionChoices.NEW)
    source = models.CharField(max_length=2, choices=SourceChoices.choices, default=SourceChoices.EXTERNAL_SUPPLIER)
    sale_status = models.CharField(max_length=2, choices=SaleStatusChoices.choices, default=SaleStatusChoices.AVAILABLE)
    grade = models.CharField(max_length=1, choices=GradeChoices.choices, null=True, blank=True)
    
    cost_of_unit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Internal Cost")
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Current Selling Price")
    
    # --- Physical Identifiers & Specs (NULL for Accessories/Laptops/Apple) ---
    serial_number = models.CharField(
        max_length=100, 
        unique=True, 
        null=True, 
        blank=True,
        help_text="Required for Phones/Laptops/Tablets. Not used for Accessories."
    )
    imei = models.CharField(max_length=15, unique=True, null=True, blank=True, 
                            help_text="IMEI for Phones/SIM-enabled Tablets")
    
    storage_gb = models.PositiveIntegerField(null=True, blank=True)
    ram_gb = models.PositiveIntegerField(null=True, blank=True)
    battery_mah = models.PositiveIntegerField(null=True, blank=True, help_text="Battery capacity in mAh")
    
    # Tablet/iPad specific
    is_sim_enabled = models.BooleanField(default=False, verbose_name="Supports SIM/Cellular")
    
    # Laptop specific
    processor_details = models.CharField(max_length=255, blank=True)
    
    # Date bought
    date_sourced = models.DateField(null=True, blank=True, help_text="Date the unit was acquired")
    
    # Reservation tracking
    reserved_by = models.ForeignKey(
        'Admin', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='reserved_units',
        help_text="Admin who has reserved this unit"
    )
    reserved_until = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Expiration date for reservation (2 days from approval)"
    )
    
    # Brand assignment
    brands = models.ManyToManyField(
        'Brand',
        related_name='inventory_units',
        blank=True,
        help_text="Brands this unit is available for. Empty = inherits from product or all brands."
    )
    
    # Online availability
    available_online = models.BooleanField(
        default=True,
        help_text="Whether this unit can be purchased online"
    )
    
    @property
    def is_reservation_expired(self):
        """Check if reservation has expired (more than 2 days old)."""
        if not self.reserved_until:
            return False
        return timezone.now() > self.reserved_until

    def __str__(self):
        return f"[{self.get_sale_status_display()}] {self.product_template.product_name} (Qty: {self.quantity})"


class InventoryUnitImage(models.Model):
    """Stores one image file linked to an Inventory Unit."""
    # This creates the one-to-many link. 'related_name' allows us to access all
    # images for a unit using unit.images.all()
    inventory_unit = models.ForeignKey(
        InventoryUnit, 
        related_name='images', 
        on_delete=models.CASCADE
    )
    # Use ImageField for storing the file upload path
    image = models.ImageField(upload_to='unit_photos/%Y/%m/')
    # Optional: Flag one image as the primary/display image
    is_primary = models.BooleanField(default=False)
    
    # Color variant shown in this image (for color selection from images)
    color = models.ForeignKey(
        'Color',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unit_images',
        help_text="Color variant shown in this image"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Image for {self.inventory_unit} (ID: {self.id})"


# -------------------------------------------------------------------------
# 4. ORDER MANAGEMENT MODELS
# -------------------------------------------------------------------------

class Order(models.Model):
    """Represents a customer's order for specific InventoryUnits."""
    class StatusChoices(models.TextChoices):
        PENDING = 'Pending', _('Pending')  # Payment not confirmed
        PAID = 'Paid', _('Paid')  # Payment confirmed - visible to Order Manager
        DELIVERED = 'Delivered', _('Delivered')
        CANCELED = 'Canceled', _('Canceled')
    
    class OrderSourceChoices(models.TextChoices):
        WALK_IN = 'WALK_IN', _('Walk-in Sale')
        ONLINE = 'ONLINE', _('Online Lead')

    order_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders', verbose_name="Ordering User", null=True, blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='orders', verbose_name="Ordering Customer")
    
    # Brand assignment
    brand = models.ForeignKey(
        'Brand',
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True
    )
    
    # Order source
    order_source = models.CharField(
        max_length=20,
        choices=OrderSourceChoices.choices,
        default=OrderSourceChoices.WALK_IN
    )
    
    # Idempotency key to prevent duplicate orders
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Idempotency key to prevent duplicate orders from retries or double-clicks"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        # Using order_id for __str__ is better since it's the primary key
        customer_name = self.customer.user.username if self.customer.user else (self.customer.name or 'Unknown')
        return f"Order #{self.order_id} by {customer_name} - {self.status}"
    
    @property
    def calculated_total(self):
        # Accesses OrderItems via the reverse relation (order_items)
        total = sum([item.sub_total for item in self.order_items.all()])
        return total

class OrderItem(models.Model):
    """Links Orders and InventoryUnits (the single physical unit sold)."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items', verbose_name="Related Order")
    
    inventory_unit = models.ForeignKey(
        'InventoryUnit', on_delete=models.SET_NULL, related_name='order_items', 
        null=True, blank=True, # Allows NULL for bulk accessory sales
        verbose_name="Stock Keeping Unit (SKU)",
        help_text="The specific InventoryUnit sold (required for unique items like phones)."
    )
    
    quantity = models.PositiveIntegerField(
        default=1, 
        help_text="Quantity of this item bought in the order."
    )
    unit_price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2, help_text="Selling price of the unit at the moment of order.",default=Decimal('0.00'))
    
    @property
    def sub_total(self):
        return self.unit_price_at_purchase * self.quantity
    
    class Meta:
        pass

    def __str__(self):
        unit_name = self.inventory_unit.product_template.product_name if self.inventory_unit else 'Bulk Item'
        return f"{unit_name} in Order #{self.order.order_id}"


# -------------------------------------------------------------------------
# 4.5. PESAPAL PAYMENT MODELS
# -------------------------------------------------------------------------

class PesapalPayment(models.Model):
    """Model to track Pesapal payment transactions."""
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        IN_PROGRESS = 'IN_PROGRESS', _('In Progress')
        COMPLETED = 'COMPLETED', _('Payment Completed')
        FAILED = 'FAILED', _('Payment Failed')
        CANCELLED = 'CANCELLED', _('Cancelled')
        EXPIRED = 'EXPIRED', _('Payment Expired')
    
    class PaymentMethodChoices(models.TextChoices):
        MPESA = 'MPESA', _('M-Pesa')
        VISA = 'VISA', _('Visa')
        MASTERCARD = 'MASTERCARD', _('Mastercard')
        AMEX = 'AMEX', _('American Express')
        MOBILE_MONEY = 'MOBILE_MONEY', _('Mobile Money')
        BANK = 'BANK', _('Bank Transfer')
        UNKNOWN = 'UNKNOWN', _('Unknown')
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='pesapal_payments')
    pesapal_order_tracking_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="Pesapal order tracking ID")
    pesapal_payment_id = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True, help_text="Pesapal payment ID (assigned after payment)")
    pesapal_reference = models.CharField(max_length=100, unique=True, db_index=True, null=True, blank=True, help_text="Pesapal payment reference")
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    payment_method = models.CharField(max_length=20, choices=PaymentMethodChoices.choices, null=True, blank=True)
    
    customer_email = models.EmailField(null=True, blank=True)
    customer_phone = models.CharField(max_length=15, null=True, blank=True)
    customer_name = models.CharField(max_length=255, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expired_at = models.DateTimeField(null=True, blank=True)
    
    ipn_data = models.JSONField(default=dict, blank=True, help_text="IPN callback data")
    api_request_data = models.JSONField(default=dict, blank=True)
    api_response_data = models.JSONField(default=dict, blank=True)
    
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    ipn_received = models.BooleanField(default=False)
    ipn_received_at = models.DateTimeField(null=True, blank=True)
    
    redirect_url = models.URLField(null=True, blank=True, help_text="Pesapal payment page URL")
    callback_url = models.URLField(null=True, blank=True, help_text="Callback URL after payment")
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['pesapal_order_tracking_id']),
            models.Index(fields=['pesapal_payment_id']),
            models.Index(fields=['pesapal_reference']),
            models.Index(fields=['status']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['customer_email']),
            models.Index(fields=['status', 'initiated_at']),
        ]
    
    def __str__(self):
        return f"Pesapal Payment for Order {self.order.order_id} - {self.status}"
    
    @property
    def is_successful(self):
        return self.status == self.StatusChoices.COMPLETED
    
    @property
    def is_expired(self):
        """Check if payment has expired."""
        if self.status == self.StatusChoices.EXPIRED:
            return True
        if self.expired_at and timezone.now() > self.expired_at:
            return True
        return False


class PesapalRefund(models.Model):
    """Model to track Pesapal refund transactions."""
    class StatusChoices(models.TextChoices):
        PENDING = 'PENDING', _('Pending')
        INITIATED = 'INITIATED', _('Refund Initiated')
        COMPLETED = 'COMPLETED', _('Refund Completed')
        FAILED = 'FAILED', _('Refund Failed')
        CANCELLED = 'CANCELLED', _('Cancelled')
    
    original_payment = models.ForeignKey('PesapalPayment', on_delete=models.CASCADE, related_name='refunds')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='pesapal_refunds')
    pesapal_refund_id = models.CharField(max_length=100, unique=True, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='KES')
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    refund_reason = models.TextField(blank=True)
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='initiated_pesapal_refunds')
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    ipn_data = models.JSONField(default=dict, blank=True)
    api_response_data = models.JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-initiated_at']
        indexes = [
            models.Index(fields=['pesapal_refund_id']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Pesapal Refund for Payment {self.original_payment.id} - {self.status}"


class PaymentNotification(models.Model):
    """Model to track payment-related notifications."""
    class NotificationTypeChoices(models.TextChoices):
        PAYMENT_INITIATED = 'PAYMENT_INITIATED', _('Payment Initiated')
        PAYMENT_COMPLETED = 'PAYMENT_COMPLETED', _('Payment Completed')
        PAYMENT_FAILED = 'PAYMENT_FAILED', _('Payment Failed')
        REFUND_INITIATED = 'REFUND_INITIATED', _('Refund Initiated')
        REFUND_COMPLETED = 'REFUND_COMPLETED', _('Refund Completed')
        PAYMENT_TIMEOUT = 'PAYMENT_TIMEOUT', _('Payment Timeout')
    
    payment = models.ForeignKey('PesapalPayment', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    refund = models.ForeignKey('PesapalRefund', on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payment_notifications')
    notification_type = models.CharField(max_length=30, choices=NotificationTypeChoices.choices)
    recipient = models.CharField(max_length=255)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['notification_type']),
            models.Index(fields=['order']),
        ]
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.recipient}"


# -------------------------------------------------------------------------
# 5. REVIEW MODEL
# -------------------------------------------------------------------------

class Review(models.Model):
    """Stores user feedback and rating for a specific Product TEMPLATE."""
    # NEW FIELD: Links the review to the Customer who wrote it
    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name='reviews', 
        verbose_name="Review Creator", null=True, blank=True,  # Allow null for admin reviews
    ) 
    
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='reviews', 
        verbose_name="Reviewed Product Template"
    )
    rating = models.IntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    comment = models.TextField()
    date_posted = models.DateTimeField(auto_now_add=True)
    
    # Video support: either upload file OR provide URL
    video_file = models.FileField(
        upload_to='review_videos/%Y/%m/',
        blank=True,
        null=True,
        verbose_name="Review Video File",
        help_text="Upload a video file from your device (max 100MB)"
    )
    video_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="Review Video Link",
        help_text="Optional link to a video (Google Drive, YouTube, etc.). If both file and URL are provided, URL takes precedence."
    )
    
    class Meta:
        ordering = ['-date_posted']
        # Optional: Prevent a customer from reviewing the same product twice
        # unique_together = ('customer', 'product') 
        
    @property
    def is_admin_review(self):
        """Returns True if review was created by an admin (customer is None)."""
        return self.customer is None
        
    def __str__(self):
        creator = self.customer.user.username if self.customer else "Admin"
        return f"Review for {self.product.product_name} - {self.rating} stars by {creator}"


# -------------------------------------------------------------------------
# 6. ADMIN ROLES & REQUEST MANAGEMENT MODELS
# -------------------------------------------------------------------------

class ReservationRequest(models.Model):
    """Model for salesperson reservation requests."""
    class StatusChoices(models.TextChoices):
        PENDING = 'PE', _('Pending')
        APPROVED = 'AP', _('Approved')
        REJECTED = 'RE', _('Rejected')
        EXPIRED = 'EX', _('Expired')
        RETURNED = 'RT', _('Returned')
    
    requesting_salesperson = models.ForeignKey(
        Admin, 
        on_delete=models.CASCADE, 
        related_name='reservation_requests',
        verbose_name="Requesting Salesperson",
        limit_choices_to={'roles__name': AdminRole.RoleChoices.SALESPERSON}
    )
    inventory_units = models.ManyToManyField(
        InventoryUnit,
        related_name='reservation_requests',
        help_text="Inventory units in this reservation request"
    )
    # Keep old field for migration compatibility (will be removed in migration)
    inventory_unit = models.ForeignKey(
        InventoryUnit,
        on_delete=models.CASCADE,
        related_name='reservation_requests_old',
        null=True,
        blank=True
    )
    status = models.CharField(max_length=2, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Auto-set to 2 days after approval")
    approved_by = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_reservation_requests',
        verbose_name="Approving Inventory Manager",
        limit_choices_to={'roles__name': AdminRole.RoleChoices.INVENTORY_MANAGER}
    )
    notes = models.TextField(blank=True, help_text="Additional notes or comments")
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name = "Reservation Request"
        verbose_name_plural = "Reservation Requests"
        # Remove unique_together since we now have multiple units per request
    
    def __str__(self):
        unit_count = self.inventory_units.count()
        if unit_count == 0 and self.inventory_unit:
            # Fallback for old single-unit requests during migration
            return f"Reservation #{self.id} - {self.inventory_unit.product_template.product_name} ({self.get_status_display()})"
        elif unit_count > 0:
            first_unit = self.inventory_units.first()
            if unit_count == 1:
                return f"Reservation #{self.id} - {first_unit.product_template.product_name} ({self.get_status_display()})"
            else:
                return f"Reservation #{self.id} - {unit_count} units ({self.get_status_display()})"
        else:
            return f"Reservation #{self.id} ({self.get_status_display()})"
    
    def save(self, *args, **kwargs):
        # Auto-set expires_at to 2 days after approval when status changes to APPROVED
        if self.status == self.StatusChoices.APPROVED and not self.expires_at:
            if self.approved_at:
                self.expires_at = self.approved_at + timedelta(days=2)
            else:
                self.expires_at = timezone.now() + timedelta(days=2)
        super().save(*args, **kwargs)


class ReturnRequest(models.Model):
    """Model for salesperson return requests (bulk returns of reserved units)."""
    class StatusChoices(models.TextChoices):
        PENDING = 'PE', _('Pending')
        APPROVED = 'AP', _('Approved')
        REJECTED = 'RE', _('Rejected')
    
    requesting_salesperson = models.ForeignKey(
        Admin,
        on_delete=models.CASCADE,
        related_name='return_requests',
        verbose_name="Requesting Salesperson",
        null=True,
        blank=True,
        limit_choices_to={'roles__name': AdminRole.RoleChoices.SALESPERSON},
        help_text="Salesperson requesting return. Null for buyback units (auto-created)."
    )
    inventory_units = models.ManyToManyField(
        InventoryUnit,
        related_name='return_requests',
        verbose_name="Units to Return"
    )
    status = models.CharField(max_length=2, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_return_requests',
        verbose_name="Approving Inventory Manager",
        limit_choices_to={'roles__name': AdminRole.RoleChoices.INVENTORY_MANAGER}
    )
    notes = models.TextField(blank=True, help_text="Optional notes from salesperson")
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name = "Return Request"
        verbose_name_plural = "Return Requests"
    
    def __str__(self):
        unit_count = self.inventory_units.count()
        return f"Return #{self.id} - {unit_count} units ({self.get_status_display()})"


class UnitTransfer(models.Model):
    """Model for transferring reserved units between salespersons."""
    class StatusChoices(models.TextChoices):
        PENDING = 'PE', _('Pending')
        APPROVED = 'AP', _('Approved')
        REJECTED = 'RE', _('Rejected')
    
    inventory_unit = models.ForeignKey(
        InventoryUnit,
        on_delete=models.CASCADE,
        related_name='transfers'
    )
    from_salesperson = models.ForeignKey(
        Admin,
        on_delete=models.CASCADE,
        related_name='outgoing_transfers',
        verbose_name="Current Salesperson",
        limit_choices_to={'roles__name': AdminRole.RoleChoices.SALESPERSON}
    )
    to_salesperson = models.ForeignKey(
        Admin,
        on_delete=models.CASCADE,
        related_name='incoming_transfers',
        verbose_name="Target Salesperson",
        limit_choices_to={'roles__name': AdminRole.RoleChoices.SALESPERSON}
    )
    status = models.CharField(max_length=2, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_transfers',
        verbose_name="Approving Inventory Manager",
        limit_choices_to={'roles__name': AdminRole.RoleChoices.INVENTORY_MANAGER}
    )
    notes = models.TextField(blank=True, help_text="Optional notes")
    
    class Meta:
        ordering = ['-requested_at']
        verbose_name = "Unit Transfer"
        verbose_name_plural = "Unit Transfers"
    
    def __str__(self):
        return f"Transfer #{self.id} - Unit {self.inventory_unit.id} from {self.from_salesperson.user.username} to {self.to_salesperson.user.username} ({self.get_status_display()})"


class Notification(models.Model):
    """Model for in-app notifications."""
    class NotificationType(models.TextChoices):
        RESERVATION_APPROVED = 'RA', _('Reservation Approved')
        RESERVATION_REJECTED = 'RR', _('Reservation Rejected')
        RESERVATION_EXPIRED = 'RE', _('Reservation Expired')
        RETURN_APPROVED = 'TA', _('Return Approved')
        RETURN_REJECTED = 'TR', _('Return Rejected')
        TRANSFER_APPROVED = 'FA', _('Transfer Approved')
        TRANSFER_REJECTED = 'FR', _('Transfer Rejected')
        ORDER_CREATED = 'OC', _('Order Created')
        UNIT_RESERVED = 'UR', _('Unit Reserved')
        REQUEST_PENDING_APPROVAL = 'RP', _('Request Pending Approval')
        NEW_LEAD = 'NL', _('New Lead')
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=2, choices=NotificationType.choices)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Generic relation to link notification to related object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username} ({'Read' if self.is_read else 'Unread'})"


# -------------------------------------------------------------------------
# 7. LEAD & CART MODELS (E-commerce Lead System)
# -------------------------------------------------------------------------

class Lead(models.Model):
    """Lead model - represents customer inquiry/interest."""
    class StatusChoices(models.TextChoices):
        NEW = 'NEW', _('New Lead')
        CONTACTED = 'CONTACTED', _('Contacted')
        CONVERTED = 'CONVERTED', _('Order Created')
        CLOSED = 'CLOSED', _('Closed - No Sale')
        EXPIRED = 'EXPIRED', _('Expired - No Response')
    
    # Customer Information
    customer_name = models.CharField(max_length=255)
    customer_phone = models.CharField(max_length=20, db_index=True)
    customer_email = models.EmailField(blank=True, null=True)
    delivery_address = models.TextField(blank=True)
    
    # Link to Customer (if exists or created)
    customer = models.ForeignKey(
        Customer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    
    # Brand Assignment
    brand = models.ForeignKey('Brand', on_delete=models.CASCADE, related_name='leads')
    
    # Lead Tracking
    lead_reference = models.CharField(max_length=50, unique=True, db_index=True)  # e.g., "LEAD-2024-001234"
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    # Status Management
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.NEW)
    assigned_salesperson = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_leads'
    )
    contacted_at = models.DateTimeField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)
    
    # Related Order (if converted)
    order = models.OneToOneField(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_lead'
    )
    
    # Notes
    salesperson_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True, help_text="Any notes from customer during submission")
    
    # Metadata
    total_value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    expires_at = models.DateTimeField(null=True, blank=True)  # 3 days from submission for NEW status
    
    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['brand', 'status']),
            models.Index(fields=['customer_phone', 'brand']),
            models.Index(fields=['status', 'expires_at']),  # For expiry queries
        ]
    
    def save(self, *args, **kwargs):
        """Auto-generate reference and set expiry."""
        if not self.lead_reference:
            # Generate reference: LEAD-YYYY-XXXXXX
            year = timezone.now().year
            last_lead = Lead.objects.filter(lead_reference__startswith=f'LEAD-{year}-').order_by('-lead_reference').first()
            if last_lead:
                try:
                    last_num = int(last_lead.lead_reference.split('-')[-1])
                    new_num = last_num + 1
                except (ValueError, IndexError):
                    new_num = 1
            else:
                new_num = 1
            self.lead_reference = f'LEAD-{year}-{new_num:06d}'
        
        # Set expiry for NEW leads (3 days)
        if not self.expires_at and self.status == Lead.StatusChoices.NEW:
            self.expires_at = timezone.now() + timedelta(days=3)
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Lead {self.lead_reference} - {self.customer_name} ({self.brand.name})"


class LeadItem(models.Model):
    """Items in a lead (tracks which units are in which leads)."""
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='items')
    inventory_unit = models.ForeignKey(InventoryUnit, on_delete=models.CASCADE, related_name='lead_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price at time of lead creation")
    
    class Meta:
        unique_together = ['lead', 'inventory_unit']
    
    def __str__(self):
        return f"{self.inventory_unit.product_template.product_name} in Lead {self.lead.lead_reference}"


class Cart(models.Model):
    """Shopping cart that becomes Lead on checkout."""
    session_key = models.CharField(max_length=40, db_index=True, blank=True)  # For anonymous users
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True)  # If recognized
    brand = models.ForeignKey('Brand', on_delete=models.CASCADE)
    
    # Contact info (collected before checkout)
    customer_name = models.CharField(max_length=255, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True, db_index=True)
    customer_email = models.EmailField(blank=True, null=True)
    delivery_address = models.TextField(blank=True, null=True)
    
    # Status
    is_submitted = models.BooleanField(default=False)  # Becomes Lead when True
    lead = models.OneToOneField(Lead, on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()  # 24 hours from creation
    
    class Meta:
        indexes = [
            models.Index(fields=['session_key', 'brand']),
            models.Index(fields=['customer_phone', 'brand']),
        ]
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Cart {self.id} - {self.brand.name} ({'Submitted' if self.is_submitted else 'Active'})"


class CartItem(models.Model):
    """Items in a shopping cart."""
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    inventory_unit = models.ForeignKey(InventoryUnit, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price at time of adding to cart (promotion price or selling_price)"
    )
    promotion = models.ForeignKey(
        'Promotion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Promotion applied to this item (if any)"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['cart', 'inventory_unit']
    
    def get_unit_price(self):
        """Return unit_price if set, otherwise selling_price."""
        return self.unit_price if self.unit_price is not None else self.inventory_unit.selling_price
    
    def __str__(self):
        return f"{self.inventory_unit.product_template.product_name} in Cart {self.cart.id}"


# -------------------------------------------------------------------------
# 8. PROMOTION TYPE MODEL (Dynamic Promotion Types)
# -------------------------------------------------------------------------

class PromotionType(models.Model):
    """Dynamic promotion types that can be added/deleted by Marketing Managers."""
    name = models.CharField(max_length=50, unique=True, help_text="Display name (e.g., 'Special Offer', 'Flash Sale')")
    code = models.CharField(max_length=10, unique=True, help_text="Short code (e.g., 'SO', 'FS')")
    description = models.TextField(blank=True, help_text="Description of this promotion type")
    is_active = models.BooleanField(default=True, help_text="Whether this type is available for use")
    display_order = models.IntegerField(default=0, help_text="Order for display in dropdowns")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = "Promotion Type"
        verbose_name_plural = "Promotion Types"
    
    def __str__(self):
        return self.name


# -------------------------------------------------------------------------
# 9. PROMOTION MODEL (E-commerce Promotions)
# -------------------------------------------------------------------------

class Promotion(models.Model):
    """Promotion model for discounts and special offers."""
    brand = models.ForeignKey('Brand', on_delete=models.CASCADE, related_name='promotions')
    promotion_type = models.ForeignKey(
        'PromotionType',
        on_delete=models.PROTECT,
        related_name='promotions',
        null=True,
        blank=True,
        help_text="Type of promotion (Special Offer, Flash Sale, etc.)"
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    banner_image = models.ImageField(
        upload_to='promotions/%Y/%m/', 
        blank=True,
        null=True,
        help_text="Banner image for promotion (required for Stories Carousel)"
    )
    promotion_code = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        help_text="Auto-generated promotion code (editable)"
    )
    display_locations = models.JSONField(
        default=list,
        help_text="List of display locations: 'stories_carousel', 'special_offers', 'flash_sales'"
    )
    carousel_position = models.IntegerField(
        null=True,
        blank=True,
        help_text="Position in stories carousel (1-5). 1 = Large banner, 2-5 = Grid positions",
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Discount details
    discount_percentage = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Discount percentage (e.g., 20.00 for 20%)"
    )
    discount_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Fixed discount amount"
    )
    
    # Promotion period
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Product targeting
    products = models.ManyToManyField(
        Product, 
        blank=True,
        related_name='promotions',
        help_text="Specific products this promotion applies to"
    )
    product_types = models.CharField(
        max_length=2, 
        choices=Product.ProductType.choices, 
        blank=True,
        help_text="All products of this type (if specified, applies to all products of this type)"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        Admin,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_promotions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['brand', 'is_active', 'start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.brand.name}"
    
    def generate_promotion_code(self):
        """Generate a unique promotion code based on promotion type."""
        import random
        import string
        
        if not self.promotion_type:
            prefix = "PROMO"
        else:
            # Use first 3-4 letters of promotion type code, uppercase
            prefix = self.promotion_type.code.upper()[:4]
        
        # Generate random alphanumeric suffix
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        code = f"{prefix}-{suffix}"
        
        # Ensure uniqueness
        while Promotion.objects.filter(promotion_code=code).exists():
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            code = f"{prefix}-{suffix}"
        
        return code
    
    def save(self, *args, **kwargs):
        """Auto-generate promotion code if not provided."""
        if not self.promotion_code:
            self.promotion_code = self.generate_promotion_code()
        super().save(*args, **kwargs)
    
    @property
    def is_currently_active(self):
        """Check if promotion is currently active."""
        from django.utils import timezone
        now = timezone.now()
        return self.is_active and self.start_date <= now <= self.end_date


# -------------------------------------------------------------------------
# 10. AUDIT LOG MODEL
# -------------------------------------------------------------------------

class AuditLog(models.Model):
    """Model for tracking all critical actions in the system."""
    class ActionType(models.TextChoices):
        CREATE = 'CR', _('Create')
        UPDATE = 'UP', _('Update')
        DELETE = 'DL', _('Delete')
        APPROVE = 'AP', _('Approve')
        REJECT = 'RJ', _('Reject')
        RESERVE = 'RS', _('Reserve')
        RELEASE = 'RL', _('Release')
        TRANSFER = 'TR', _('Transfer')
        ARCHIVE = 'AR', _('Archive')
        BULK_UPDATE = 'BU', _('Bulk Update')
        PRICE_CHANGE = 'PC', _('Price Change')
        STATUS_CHANGE = 'SC', _('Status Change')
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        help_text="User who performed the action"
    )
    action = models.CharField(max_length=2, choices=ActionType.choices)
    model_name = models.CharField(max_length=100, help_text="Name of the model affected")
    object_id = models.PositiveIntegerField(help_text="ID of the affected object")
    object_repr = models.CharField(max_length=255, blank=True, help_text="String representation of the object")
    
    # Store changes as JSON
    old_value = models.JSONField(null=True, blank=True, help_text="Previous state (for updates)")
    new_value = models.JSONField(null=True, blank=True, help_text="New state (for creates/updates)")
    
    # Additional context
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Generic relation to link audit log to related object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'user']),
            models.Index(fields=['model_name', '-timestamp']),
        ]
    
    def __str__(self):
        user_str = self.user.username if self.user else 'System'
        return f"{user_str} - {self.get_action_display()} - {self.model_name} #{self.object_id}"
    
    @classmethod
    def log_action(cls, user, action, obj, old_data=None, new_data=None, request=None):
        """
        Create an audit log entry.
        
        Args:
            user: User object who performed the action
            action: ActionType choice (e.g., 'CR', 'UP', 'DL')
            obj: The model instance being logged
            old_data: Dict of old values (for updates)
            new_data: Dict of new values (for creates/updates)
            request: HttpRequest object (to extract IP, user agent)
        """
        ip_address = None
        user_agent = ''
        
        if request:
            # Extract IP address
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Extract user agent
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return cls.objects.create(
            user=user,
            action=action,
            model_name=obj.__class__.__name__,
            object_id=obj.pk,
            object_repr=str(obj)[:255],
            old_value=old_data,
            new_value=new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            content_type=ContentType.objects.get_for_model(obj),
        )


# -------------------------------------------------------------------------
# 10. RECEIPT MODEL
# -------------------------------------------------------------------------

class Receipt(models.Model):
    """Model to store generated receipts for orders."""
    order = models.OneToOneField(
        Order, 
        on_delete=models.CASCADE, 
        related_name='receipt',
        verbose_name="Related Order"
    )
    receipt_number = models.CharField(
        max_length=50, 
        unique=True,
        help_text="Unique receipt number (e.g., SL_1121)"
    )
    pdf_file = models.FileField(
        upload_to='receipts/%Y/%m/',
        null=True,
        blank=True,
        help_text="Generated PDF receipt file"
    )
    html_content = models.TextField(
        blank=True,
        help_text="HTML content of the receipt"
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_sent = models.BooleanField(default=False)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-generated_at']
        verbose_name = "Receipt"
        verbose_name_plural = "Receipts"
    
    def __str__(self):
        return f"Receipt {self.receipt_number} for Order {self.order.order_id}"
