from django.contrib import admin
# Importing all models needed for the Admin panel. 
# Assuming all models exist in the inventory/models.py file.
from .models import (
    Product, ProductAccessory, Review, Color, 
    UnitAcquisitionSource, InventoryUnit, Order, 
    OrderItem, Customer, Admin, ProductImage, InventoryUnitImage, Promotion, Brand,
    PesapalPayment, PesapalRefund, PaymentNotification
)

# --- INLINE CLASSES ---

class ProductImageInline(admin.TabularInline):
    """Inline for editing the images linked to a Product."""
    # This model is the intermediate table (the images themselves)
    model = ProductImage 
    # Sets how many blank forms to show
    extra = 1     
    # Assuming ProductImage has a field named 'image' which holds the file.
    # You can list other fields here too, like 'caption' or 'sort_order'.
    fields = ['image',] 

class InventoryUnitImageInline(admin.TabularInline):
    """Inline for editing the images linked to an Inventory Unit."""
    model = InventoryUnitImage
    extra = 1
    fields = ['image', 'is_primary']

class ProductAccessoryInline(admin.TabularInline):
    """Inline for editing the accessories linked to a main Product."""
    model = ProductAccessory
    fk_name = 'main_product' 
    extra = 1

class OrderItemInline(admin.TabularInline):
    """Inline for viewing all items linked to a specific Order."""
    model = OrderItem
    extra = 0
    # Display and security settings for items in a completed order
    readonly_fields = ('inventory_unit', 'quantity', 'unit_price_at_purchase', 'sub_total')
    can_delete = False 

# --- CORE INVENTORY MANAGEMENT ---

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Customizes how the Product model appears in the Admin."""
    
    list_display = (
        'product_name', 'product_type', 'brand', 'model_series', 'created_at'
    )
    list_filter = ('product_type', 'brand') 
    search_fields = ('product_name', 'product_type', 'brand', 'model_series')

    fieldsets = (
        ('Core Details', {
            'fields': ('product_name', 'brand', 'model_series', 'product_type')
        }),
        # FIXED: Removed 'product_image' from the fields list, as it's handled by the Inline.
        ('Description & Media', {
            'fields': ('product_description',),
        }),
    )

    # ADDED ProductImageInline to the list of inlines
    inlines = [ProductAccessoryInline, ProductImageInline]

    # REMOVED: is_available_status as the logic now lives primarily on InventoryUnit.
    # We will trust the list_display is now purely descriptive fields for the Product template.

@admin.register(InventoryUnit)
class InventoryUnitAdmin(admin.ModelAdmin):
    """Admin view for tracking individual physical stock units."""
    list_display = (
        'serial_number', 'product_template', 'condition', 'grade', 
        'sale_status', 'available_online', 'selling_price', 'date_sourced'
    )
    list_select_related = ('product_template', 'product_color') 
    list_filter = ('sale_status', 'available_online', 'condition', 'grade', 'source')
    # CONSISTENT: Using product_template__product_name for searching.
    search_fields = (
        'serial_number', 'imei', 'product_template__product_name', 
        'acquisition_source_details__name'
    )
    
    fieldsets = (
        ('Product Identification', {
            'fields': ('product_template', 'product_color', 'serial_number', 'imei', 'quantity')
        }),
        ('Unit Status', {
            'fields': ('condition', 'grade', 'sale_status', 'available_online', 'selling_price', 'cost_of_unit')
        }),
        ('Source & Date', {
            'fields': ('source', 'acquisition_source_details', 'date_sourced')
        }),
        ('Technical Specs', {
            'fields': ('storage_gb', 'ram_gb', 'is_sim_enabled', 'processor_details')
        }),
    )
    
    inlines = [InventoryUnitImageInline]

@admin.register(ProductAccessory)
class ProductAccessoryAdmin(admin.ModelAdmin):
    """Customizes how the ProductAccessory link model appears in the Admin for direct management."""
    
    list_display = (
        'main_product', 
        'accessory', 
        'required_quantity', 
        'main_product_type', 
        'accessory_type'
    )
    
    list_filter = (
        'main_product__product_type', 
        'required_quantity'
    )
    
    # CONSISTENT: Using product_name across relationships
    search_fields = (
        'main_product__product_name', 
        'accessory__product_name'
    )
    
    def main_product_type(self, obj):
        """Displays the type of the main product."""
        return obj.main_product.get_product_type_display()
    main_product_type.short_description = 'Main Type'
    
    def accessory_type(self, obj):
        """Displays the type of the accessory product."""
        return obj.accessory.get_product_type_display()
    accessory_type.short_description = 'Accessory Type'

# --- SALES AND USER MANAGEMENT ---

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Comprehensive Admin view for tracking customer orders."""
    list_display = (
        'order_id', 'customer', 'status', 'total_amount', 'created_at'
    )
    list_select_related = ('customer', 'user') # Use 'user' for consistency with model structure
    list_filter = ('status', 'created_at')
    search_fields = ('order_id', 'customer__user__username', 'customer__user__email')
    readonly_fields = ('order_id', 'created_at', 'total_amount')
    
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Details', {
            'fields': ('order_id', 'customer', 'status', 'created_at', 'total_amount')
        }),
    )

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Customizes how the Review model appears in the Admin."""
    # CORRECTED: Added 'customer' to list_display
    list_display = ('product', 'customer', 'rating', 'comment_snippet', 'date_posted')
    # CORRECTED: Added 'customer' to list_filter
    list_filter = ('rating', 'date_posted', 'customer')
    # CONSISTENT: Using customer__user__username for searching by owner.
    search_fields = ('comment', 'product__product_name', 'customer__user__username')
    
    def comment_snippet(self, obj):
        """Displays a truncated version of the comment."""
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_snippet.short_description = 'Comment'

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin view for managing Customer profiles."""
    list_display = ('user', 'phone_number')
    list_select_related = ('user',)
    search_fields = ('user__username', 'user__email', 'phone_number')

@admin.register(Admin)
class AdminProfileAdmin(admin.ModelAdmin):
    """Admin view for managing Admin profiles."""
    list_display = ('user', 'admin_code')
    list_select_related = ('user',)
    search_fields = ('user__username', 'user__email', 'admin_code')


# --- LOOKUP TABLES / UTILITIES ---

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    """Admin view for managing the Color lookup table."""
    list_display = ('name', 'hex_code')
    search_fields = ('name', 'hex_code')

@admin.register(UnitAcquisitionSource)
class UnitAcquisitionSourceAdmin(admin.ModelAdmin):
    """Admin view for managing supplier/import partner details."""
    list_display = ('name', 'source_type', 'phone_number')
    list_filter = ('source_type',)
    search_fields = ('name', 'phone_number')

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    """Admin view for managing promotions and special offers."""
    list_display = ('title', 'brand', 'discount_percentage', 'discount_amount', 'start_date', 'end_date', 'is_active', 'is_currently_active')
    list_filter = ('brand', 'is_active', 'start_date', 'end_date', 'product_types')
    search_fields = ('title', 'description')
    date_hierarchy = 'start_date'
    filter_horizontal = ('products',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('brand', 'title', 'description', 'banner_image')
        }),
        ('Discount Details', {
            'fields': ('discount_percentage', 'discount_amount'),
            'description': 'Use either percentage or fixed amount, not both'
        }),
        ('Promotion Period', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Product Targeting', {
            'fields': ('product_types', 'products'),
            'description': 'Apply to all products of a type, or select specific products. Leave both empty for site-wide promotions.'
        }),
    )
    
    def is_currently_active(self, obj):
        """Display if promotion is currently active based on dates and status."""
        return obj.is_currently_active
    is_currently_active.boolean = True
    is_currently_active.short_description = 'Currently Active'

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin view for managing company brands."""
    list_display = ('code', 'name', 'is_active', 'ecommerce_domain')
    list_filter = ('is_active',)
    search_fields = ('code', 'name', 'ecommerce_domain')
    fields = ('code', 'name', 'description', 'is_active', 'logo', 'primary_color', 'ecommerce_domain')

@admin.register(PesapalPayment)
class PesapalPaymentAdmin(admin.ModelAdmin):
    """Admin view for managing Pesapal payments."""
    list_display = ('order', 'customer_email', 'amount', 'currency', 'status', 'payment_method', 'pesapal_order_tracking_id', 'initiated_at', 'completed_at')
    list_filter = ('status', 'payment_method', 'currency', 'initiated_at', 'is_verified')
    search_fields = ('order__order_id', 'pesapal_order_tracking_id', 'pesapal_payment_id', 'pesapal_reference', 'customer_email', 'customer_phone')
    readonly_fields = ('initiated_at', 'completed_at', 'expired_at', 'verified_at', 'ipn_received_at')
    fieldsets = (
        ('Order & Payment', {
            'fields': ('order', 'amount', 'currency', 'status', 'payment_method')
        }),
        ('Pesapal Details', {
            'fields': ('pesapal_order_tracking_id', 'pesapal_payment_id', 'pesapal_reference', 'redirect_url', 'callback_url')
        }),
        ('Customer Information', {
            'fields': ('customer_email', 'customer_phone', 'customer_name')
        }),
        ('Verification', {
            'fields': ('is_verified', 'verified_at', 'ipn_received', 'ipn_received_at')
        }),
        ('Timestamps', {
            'fields': ('initiated_at', 'completed_at', 'expired_at')
        }),
    )

@admin.register(PesapalRefund)
class PesapalRefundAdmin(admin.ModelAdmin):
    """Admin view for managing Pesapal refunds."""
    list_display = ('order', 'original_payment', 'amount', 'currency', 'status', 'initiated_at', 'completed_at')
    list_filter = ('status', 'currency', 'initiated_at')
    search_fields = ('order__order_id', 'pesapal_refund_id')
    readonly_fields = ('initiated_at', 'completed_at')

@admin.register(PaymentNotification)
class PaymentNotificationAdmin(admin.ModelAdmin):
    """Admin view for managing payment notifications."""
    list_display = ('order', 'notification_type', 'recipient', 'created_at')
    list_filter = ('notification_type', 'created_at')
    search_fields = ('order__order_id', 'recipient', 'message')
    readonly_fields = ('created_at',)
