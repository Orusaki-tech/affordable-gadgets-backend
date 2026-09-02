from django import forms
from django.contrib import admin
from django.utils.html import format_html

# Importing all models needed for the Admin panel.
# Assuming all models exist in the inventory/models.py file.
from .models import (
    Admin,
    ArticleImage,
    Brand,
    Color,
    Customer,
    FinancingOffer,
    FinancingProvider,
    InventoryUnit,
    InventoryUnitImage,
    Order,
    OrderItem,
    PaymentNotification,
    PesapalPayment,
    PesapalRefund,
    Product,
    ProductAccessory,
    ProductArticle,
    ProductImage,
    ProductReleaseDate,
    ProductVariant,
    Promotion,
    Review,
    Tag,
    UnitAcquisitionSource,
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
    fields = [
        "image",
    ]


class InventoryUnitImageInline(admin.TabularInline):
    """Inline for editing the images linked to an Inventory Unit."""

    model = InventoryUnitImage
    extra = 1
    fields = ["image", "is_primary"]


class ArticleImageInline(admin.TabularInline):
    """Inline for editing images embedded in a ProductArticle."""

    model = ArticleImage
    extra = 1
    fields = ["image", "alt_text", "caption", "position", "markdown_snippet"]
    readonly_fields = ["markdown_snippet"]

    def markdown_snippet(self, obj):
        """Returns a copy-pasteable markdown snippet for the image."""
        if obj.pk and obj.image:
            return format_html("<code>![{}]({})</code>", obj.alt_text or "image", obj.image.url)
        return "Save to see snippet"

    markdown_snippet.short_description = "Markdown Snippet"


class ProductArticleInline(admin.StackedInline):
    """Inline for editing the buying guide linked to a Product."""

    model = ProductArticle
    extra = 1
    max_num = 20
    fields = ["slug", "category", "headline", "seo_title", "seo_description", "body", "is_published", "is_primary"]
    verbose_name = "Buying Guide / Blog Content"
    verbose_name_plural = "Buying Guide / Blog Content"


class ProductAccessoryInline(admin.TabularInline):
    """Inline for editing the accessories linked to a main Product."""

    model = ProductAccessory
    fk_name = "main_product"
    extra = 1


class ProductVariantInline(admin.TabularInline):
    """Inline for editing product variants (storage/RAM combinations)."""

    model = ProductVariant
    extra = 1
    fields = ("storage_gb", "ram_gb", "default_selling_price", "default_cost_of_unit", "is_active")


class OrderItemInline(admin.TabularInline):
    """Inline for viewing all items linked to a specific Order."""

    model = OrderItem
    extra = 0
    # Display and security settings for items in a completed order
    readonly_fields = ("inventory_unit", "quantity", "unit_price_at_purchase", "sub_total")
    can_delete = False


# --- CORE INVENTORY MANAGEMENT ---


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Customizes how the Product model appears in the Admin."""

    list_display = (
        "product_name", "product_type", "brand",
        "storage_gb", "ram_gb", "release_date", "created_at"
    )
    list_filter = ("product_type", "brand")
    search_fields = ("product_name", "product_type", "brand", "model_series")

    fieldsets = (
        ("Core Details", {"fields": ("product_name", "brand", "model_series", "product_type", "release_date")}),
        (
            "Storage & RAM",
            {
                "fields": ("storage_gb", "ram_gb"),
                "description": "Set storage and RAM directly on the product (e.g., 128GB, 8GB). "
                "Use ProductVariants below for multiple storage/RAM options.",
            },
        ),
        (
            "Pricing",
            {
                "fields": ("default_selling_price",),
                "description": "Shown when no listable units; seeds unit selling price if omitted on create.",
            },
        ),
        (
            "Description & Media",
            {
                "fields": ("product_description",),
            },
        ),
    )

    # ADDED ProductImageInline and ProductArticleInline to the list of inlines
    inlines = [ProductAccessoryInline, ProductImageInline, ProductArticleInline, ProductVariantInline]

    class Media:
        js = ("admin/js/char_counter.js",)


@admin.register(InventoryUnit)
class InventoryUnitAdmin(admin.ModelAdmin):
    """Admin view for tracking individual physical stock units."""

    list_display = (
        "serial_number",
        "product_template",
        "condition",
        "grade",
        "sale_status",
        "available_online",
        "selling_price",
        "date_sourced",
    )
    list_select_related = ("product_template", "product_color")
    list_filter = ("sale_status", "available_online", "condition", "grade", "source")
    # CONSISTENT: Using product_template__product_name for searching.
    search_fields = (
        "serial_number",
        "imei",
        "product_template__product_name",
        "acquisition_source_details__name",
    )

    fieldsets = (
        (
            "Product Identification",
            {"fields": ("product_template", "product_color", "serial_number", "imei", "quantity")},
        ),
        (
            "Unit Status",
            {
                "fields": (
                    "condition",
                    "grade",
                    "sale_status",
                    "available_online",
                    "selling_price",
                    "cost_of_unit",
                )
            },
        ),
        ("Source & Date", {"fields": ("source", "acquisition_source_details", "date_sourced")}),
        (
            "Technical Specs",
            {"fields": ("storage_gb", "ram_gb", "is_sim_enabled", "processor_details")},
        ),
    )

    inlines = [InventoryUnitImageInline]


@admin.register(ProductAccessory)
class ProductAccessoryAdmin(admin.ModelAdmin):
    """Customizes how the ProductAccessory link model appears in the Admin for direct management."""

    list_display = (
        "main_product",
        "accessory",
        "required_quantity",
        "main_product_type",
        "accessory_type",
    )

    list_filter = ("main_product__product_type", "required_quantity")

    # CONSISTENT: Using product_name across relationships
    search_fields = ("main_product__product_name", "accessory__product_name")

    def main_product_type(self, obj):
        """Displays the type of the main product."""
        return obj.main_product.get_product_type_display()

    main_product_type.short_description = "Main Type"

    def accessory_type(self, obj):
        """Displays the type of the accessory product."""
        return obj.accessory.get_product_type_display()

    accessory_type.short_description = "Accessory Type"


@admin.register(ProductArticle)
class ProductArticleAdmin(admin.ModelAdmin):
    """Admin view for managing product buying guides independently."""

    list_display = (
        "product",
        "headline",
        "category",
        "is_published",
        "published_at",
        "updated_at",
        "tag_list",
    )
    list_filter = ("category", "is_published", "created_at", "tags")
    search_fields = ("product__product_name", "headline", "body", "tags__name")
    filter_horizontal = ("tags", "products")
    inlines = [ArticleImageInline]
    readonly_fields = ("published_at", "created_at", "updated_at", "thumbnail_preview")

    def tag_list(self, obj):
        return ", ".join(t.name for t in obj.tags.all()) or "-"
    tag_list.short_description = "Tags"

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "category",
                    "headline",
                ),
                "classes": ("wide",),
            },
        ),
        (
            "Media",
            {
                "fields": (
                    "thumbnail_image",
                    "thumbnail_preview",
                ),
            },
        ),
        (
            "Content",
            {
                "fields": ("body", "is_published"),
            },
        ),
        (
            "Tags",
            {
                "fields": ("tags",),
                "description": "Add tags like 'featured' to control which blogs appear on featured products. Like Product tags.",
            },
        ),
        (
            "SEO & Meta",
            {
                "fields": ("seo_title", "seo_description"),
                "classes": ("collapse",),
            },
        ),
        (
            "Linkage",
            {
                "fields": ("product", "products"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("published_at", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def thumbnail_preview(self, obj):
        if obj.thumbnail_image:
            return format_html(
                '<img src="{}" style="max-height: 200px; border-radius: 8px;" />',
                obj.thumbnail_image.url,
            )
        return "No thumbnail uploaded"

    thumbnail_preview.short_description = "Preview"

    class Media:
        js = ("admin/js/char_counter.js",)
        css = {
            "all": ("admin/css/modern_blog.css",),
        }


@admin.register(ArticleImage)
class ArticleImageAdmin(admin.ModelAdmin):
    """Admin view for managing article images."""

    list_display = ("id", "article", "image", "position", "created_at")
    list_filter = ("created_at",)
    search_fields = ("article__product__product_name", "alt_text", "caption")


# --- SALES AND USER MANAGEMENT ---


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Comprehensive Admin view for tracking customer orders."""

    list_display = ("order_id", "customer", "status", "total_amount", "created_at")
    list_select_related = ("customer", "user")  # Use 'user' for consistency with model structure
    list_filter = ("status", "created_at")
    search_fields = ("order_id", "customer__user__username", "customer__user__email")
    readonly_fields = ("order_id", "created_at", "total_amount")

    inlines = [OrderItemInline]

    fieldsets = (
        (
            "Order Details",
            {"fields": ("order_id", "customer", "status", "created_at", "total_amount")},
        ),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Customizes how the Review model appears in the Admin."""

    # CORRECTED: Added 'customer' to list_display
    list_display = ("product", "customer", "rating", "comment_snippet", "date_posted")
    # CORRECTED: Added 'customer' to list_filter
    list_filter = ("rating", "date_posted", "customer")
    # CONSISTENT: Using customer__user__username for searching by owner.
    search_fields = ("comment", "product__product_name", "customer__user__username")

    def comment_snippet(self, obj):
        """Displays a truncated version of the comment."""
        return obj.comment[:50] + "..." if len(obj.comment) > 50 else obj.comment

    comment_snippet.short_description = "Comment"


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin view for managing Customer profiles."""

    list_display = ("user", "phone_number")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email", "phone_number")


@admin.register(Admin)
class AdminProfileAdmin(admin.ModelAdmin):
    """Admin view for managing Admin profiles."""

    list_display = ("user", "admin_code")
    list_select_related = ("user",)
    search_fields = ("user__username", "user__email", "admin_code")


# --- LOOKUP TABLES / UTILITIES ---


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    """Admin view for managing the Color lookup table."""

    list_display = ("name", "hex_code")
    search_fields = ("name", "hex_code")


@admin.register(UnitAcquisitionSource)
class UnitAcquisitionSourceAdmin(admin.ModelAdmin):
    """Admin view for managing supplier/import partner details."""

    list_display = ("name", "source_type", "phone_number")
    list_filter = ("source_type",)
    search_fields = ("name", "phone_number")


DISPLAY_LOCATION_CHOICES = [
    ("stories_carousel", "Stories carousel"),
    ("special_offers", "Special offers"),
    ("flash_sales", "Flash sales"),
    ("homepage_hero", "Homepage hero"),
]


class PromotionAdminForm(forms.ModelForm):
    """Form with checkbox selection for display_locations so admins can tick 'Homepage hero' etc."""

    display_locations = forms.MultipleChoiceField(
        choices=DISPLAY_LOCATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text="Tick 'Homepage hero' to show this promotion in the homepage hero carousel.",
    )

    class Meta:
        model = Promotion
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and isinstance(self.instance.display_locations, list):
            self.fields["display_locations"].initial = self.instance.display_locations

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.display_locations = self.cleaned_data.get("display_locations") or []
        if commit:
            instance.save()
        return instance


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    """Admin view for managing promotions and special offers."""

    form = PromotionAdminForm

    list_display = (
        "title",
        "brand",
        "discount_percentage",
        "discount_amount",
        "start_date",
        "end_date",
        "is_active",
        "is_currently_active",
    )
    list_filter = ("brand", "is_active", "start_date", "end_date", "product_types")
    search_fields = ("title", "description")
    date_hierarchy = "start_date"
    filter_horizontal = ("products",)

    fieldsets = (
        ("Basic Information", {"fields": ("brand", "title", "description", "banner_image")}),
        (
            "Discount Details",
            {
                "fields": ("discount_percentage", "discount_amount", "featured_sale_price"),
                "description": "Use either percentage or fixed amount, not both",
            },
        ),
        ("Promotion Period", {"fields": ("start_date", "end_date", "is_active")}),
        (
            "Product Targeting",
            {
                "fields": ("product_types", "products", "featured_product"),
                "description": "Apply to all products of a type, or select specific products. Choose a featured product when this promotion needs a storefront promo card.",
            },
        ),
        (
            "Display & placement",
            {
                "fields": ("display_locations", "carousel_position", "promotion_code"),
                "description": "Tick 'Homepage hero' to show this promotion in the homepage hero carousel. Use carousel_position to control order (lower = earlier).",
            },
        ),
    )

    def is_currently_active(self, obj):
        """Display if promotion is currently active based on dates and status."""
        return obj.is_currently_active

    is_currently_active.boolean = True
    is_currently_active.short_description = "Currently Active"


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin view for managing company brands."""

    list_display = ("code", "name", "is_active", "ecommerce_domain")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "ecommerce_domain")
    fields = (
        "code",
        "name",
        "description",
        "is_active",
        "logo",
        "primary_color",
        "ecommerce_domain",
    )


@admin.register(FinancingProvider)
class FinancingProviderAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    fields = ("name", "slug", "logo", "is_active")


@admin.register(FinancingOffer)
class FinancingOfferAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "product",
        "rom_gb",
        "ram_gb",
        "deposit_amount",
        "retail_amount",
        "monthly_payment",
        "is_active",
        "updated_at",
    )
    list_select_related = ("provider", "product")
    list_filter = ("provider", "is_active")
    search_fields = ("product__product_name", "provider__name")
    fields = (
        "provider",
        "product",
        "rom_gb",
        "ram_gb",
        "deposit_amount",
        "retail_amount",
        "daily_payment",
        "weekly_payment",
        "monthly_payment",
        "is_active",
    )


@admin.register(PesapalPayment)
class PesapalPaymentAdmin(admin.ModelAdmin):
    """Admin view for managing Pesapal payments."""

    list_display = (
        "order",
        "customer_email",
        "amount",
        "currency",
        "status",
        "payment_method",
        "pesapal_order_tracking_id",
        "initiated_at",
        "completed_at",
    )
    list_filter = ("status", "payment_method", "currency", "initiated_at", "is_verified")
    search_fields = (
        "order__order_id",
        "pesapal_order_tracking_id",
        "pesapal_payment_id",
        "pesapal_reference",
        "customer_email",
        "customer_phone",
    )
    readonly_fields = (
        "initiated_at",
        "completed_at",
        "expired_at",
        "verified_at",
        "ipn_received_at",
    )
    fieldsets = (
        (
            "Order & Payment",
            {"fields": ("order", "amount", "currency", "status", "payment_method")},
        ),
        (
            "Pesapal Details",
            {
                "fields": (
                    "pesapal_order_tracking_id",
                    "pesapal_payment_id",
                    "pesapal_reference",
                    "redirect_url",
                    "callback_url",
                )
            },
        ),
        ("Customer Information", {"fields": ("customer_email", "customer_phone", "customer_name")}),
        (
            "Verification",
            {"fields": ("is_verified", "verified_at", "ipn_received", "ipn_received_at")},
        ),
        ("Timestamps", {"fields": ("initiated_at", "completed_at", "expired_at")}),
    )


@admin.register(PesapalRefund)
class PesapalRefundAdmin(admin.ModelAdmin):
    """Admin view for managing Pesapal refunds."""

    list_display = (
        "order",
        "original_payment",
        "amount",
        "currency",
        "status",
        "initiated_at",
        "completed_at",
    )
    list_filter = ("status", "currency", "initiated_at")
    search_fields = ("order__order_id", "pesapal_refund_id")
    readonly_fields = ("initiated_at", "completed_at")


@admin.register(PaymentNotification)
class PaymentNotificationAdmin(admin.ModelAdmin):
    """Admin view for managing payment notifications."""

    list_display = ("order", "notification_type", "recipient", "created_at")
    list_filter = ("notification_type", "created_at")
    search_fields = ("order__order_id", "recipient", "message")
    readonly_fields = ("created_at",)


@admin.register(ProductReleaseDate)
class ProductReleaseDateAdmin(admin.ModelAdmin):
    list_display = ("family_key", "product_label", "release_month", "release_year", "source_url", "updated_at")
    list_filter = ("release_year", "release_month")
    search_fields = ("family_key", "product_label", "notes")
    readonly_fields = ("updated_at",)
    ordering = ("-release_year", "-release_month", "family_key")
