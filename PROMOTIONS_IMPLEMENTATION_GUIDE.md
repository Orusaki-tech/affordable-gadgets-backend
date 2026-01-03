# Promotions/Special Offers Implementation Guide

## Current Status

✅ **Backend is fully implemented:**
- `Promotion` model with all necessary fields
- API endpoints for creating/updating promotions
- Public API for frontend to fetch active promotions
- Brand-based filtering

✅ **Frontend is ready:**
- `SpecialOffers` component fetches and displays promotions
- Placeholder cards shown when no promotions exist
- Clickable cards that navigate to promotion details

## Who Should Manage Promotions?

### ❌ **NOT Inventory Managers**

**Inventory Managers** should **NOT** manage promotions because:
- Their role is focused on **physical stock management**
- They handle: unit transfers, reservation approvals, return requests, stock levels
- Promotions are a **marketing/sales function**, not inventory management

### ✅ **Recommended: Superusers or Admins**

Currently, **any staff user** (`IsAdminUser` permission) can manage promotions. This is appropriate for:
- **Superusers** - Full system access
- **Global Admins** - Admins with access to all brands
- **Brand-specific Admins** - Can manage promotions for their assigned brands

### 🎯 **Future: Marketing Manager Role (Optional)**

If you want to create a dedicated role, you could add:
- **"Marketing Manager" (MM)** role
- Specific permissions for promotion management
- This would be cleaner separation of concerns

## How to Implement Special Offers

### Method 1: Via Django Admin (Easiest)

1. **Register Promotion in Django Admin:**

Add to `inventory/admin.py`:
```python
from .models import Promotion

@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
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
            'fields': ('discount_percentage', 'discount_amount')
        }),
        ('Promotion Period', {
            'fields': ('start_date', 'end_date', 'is_active')
        }),
        ('Product Targeting', {
            'fields': ('product_types', 'products'),
            'description': 'Apply to all products of a type, or specific products'
        }),
    )
    
    def is_currently_active(self, obj):
        return obj.is_currently_active
    is_currently_active.boolean = True
    is_currently_active.short_description = 'Currently Active'
```

2. **Access Django Admin:**
   - Go to `http://localhost:8000/admin/`
   - Login as superuser
   - Navigate to **Inventory → Promotions**
   - Click **Add Promotion**

3. **Fill in the form:**
   - **Brand**: Select the brand (e.g., AFFORDABLE_GADGETS)
   - **Title**: "Flash Sale", "New Arrivals", "Weekend Deal"
   - **Description**: "Limited time offer", "Latest products", etc.
   - **Banner Image**: Upload an image (optional, but recommended)
   - **Discount Percentage**: e.g., `50.00` for 50% OFF
   - **Start Date**: When promotion starts
   - **End Date**: When promotion ends
   - **Is Active**: Check to enable
   - **Product Types**: Optional - apply to all phones, laptops, etc.
   - **Products**: Optional - select specific products

### Method 2: Via API (For Admin Frontend)

The API is already available at `/api/inventory/promotions/`

**Create Promotion:**
```bash
POST /api/inventory/promotions/
Headers:
  Authorization: Token <admin_token>
  Content-Type: multipart/form-data

Body:
{
  "brand": 1,  # Brand ID
  "title": "Flash Sale",
  "description": "Limited time offer",
  "banner_image": <file>,
  "discount_percentage": "50.00",
  "start_date": "2025-11-10T00:00:00Z",
  "end_date": "2025-11-17T23:59:59Z",
  "is_active": true,
  "product_types": "PH"  # Optional: PH, LT, TB, AC
}
```

**Update Promotion:**
```bash
PATCH /api/inventory/promotions/{id}/
Headers:
  Authorization: Token <admin_token>

Body:
{
  "is_active": false,  # Disable promotion
  "end_date": "2025-11-20T23:59:59Z"  # Extend promotion
}
```

### Method 3: Create Admin UI Page (Recommended)

Create a Promotions management page in the admin frontend similar to other pages.

**Location:** `frontend_inventory_and_orders/inventory-management-frontend/src/pages/PromotionsPage.tsx`

This would allow admins to:
- View all promotions
- Create new promotions
- Edit existing promotions
- Upload banner images
- Set start/end dates
- Enable/disable promotions
- Assign to specific products or product types

## Promotion Model Fields Explained

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `brand` | ForeignKey | Which brand this promotion belongs to | AFFORDABLE_GADGETS |
| `title` | CharField | Promotion title | "Flash Sale" |
| `description` | TextField | Promotion description | "Limited time offer" |
| `banner_image` | ImageField | Banner image for display | Upload image file |
| `discount_percentage` | Decimal | Percentage discount | `50.00` = 50% OFF |
| `discount_amount` | Decimal | Fixed amount discount | `1000.00` = KES 1000 OFF |
| `start_date` | DateTime | When promotion starts | `2025-11-10 00:00:00` |
| `end_date` | DateTime | When promotion ends | `2025-11-17 23:59:59` |
| `is_active` | Boolean | Enable/disable promotion | `true` |
| `product_types` | CharField | Apply to all products of this type | `PH` (Phones), `LT` (Laptops) |
| `products` | ManyToMany | Specific products (if not using product_types) | Select individual products |

## How Frontend Displays Promotions

1. **Frontend fetches promotions:**
   - API: `GET /api/v1/public/promotions/`
   - Automatically filtered by brand (via `X-Brand-Code` header)
   - Only shows active promotions within date range

2. **SpecialOffers component:**
   - Displays up to 5 promotions
   - Shows banner image if available
   - Displays discount (e.g., "50% OFF")
   - Clickable cards navigate to `/promotions/{id}`

3. **Placeholder cards:**
   - Shown when no promotions exist
   - Gradient backgrounds with icons
   - Same visual style as real promotions

## Best Practices

1. **Banner Images:**
   - Recommended size: 800x400px or similar aspect ratio
   - Format: JPG or PNG
   - Should be visually appealing and match brand colors

2. **Discount Strategy:**
   - Use `discount_percentage` for percentage-based discounts (most common)
   - Use `discount_amount` for fixed amount discounts
   - Don't use both at the same time

3. **Product Targeting:**
   - Use `product_types` to apply to all products of a type (e.g., all phones)
   - Use `products` for specific product promotions
   - Leave both empty for site-wide promotions (future feature)

4. **Date Management:**
   - Always set realistic start and end dates
   - Use `is_active` to quickly enable/disable without deleting
   - Check `is_currently_active` property to see if promotion is live

5. **Brand Filtering:**
   - Each promotion belongs to one brand
   - Admins only see promotions for their assigned brands
   - Superusers see all promotions

## Example: Creating a "Flash Sale" Promotion

**Via Django Admin:**
1. Go to `/admin/inventory/promotion/add/`
2. Fill in:
   - Brand: AFFORDABLE_GADGETS
   - Title: "Flash Sale"
   - Description: "Limited time offer - 50% off selected items"
   - Banner Image: Upload flash_sale_banner.jpg
   - Discount Percentage: `50.00`
   - Start Date: `2025-11-10 00:00:00`
   - End Date: `2025-11-17 23:59:59`
   - Is Active: ✓
   - Product Types: `PH` (or leave empty for all products)
3. Click "Save"

**Result:**
- Promotion appears on frontend immediately
- Shows "50% OFF" on the card
- Displays banner image
- Automatically expires on end date

## Troubleshooting

**Promotions not showing on frontend:**
- Check `is_active = True`
- Verify dates: `start_date <= now <= end_date`
- Check brand matches frontend brand code
- Check API endpoint: `/api/v1/public/promotions/`

**Permission errors:**
- Ensure user is staff (`is_staff = True`)
- Check user has Admin profile
- Verify brand assignment if not superuser

## Next Steps

1. **Add Promotion to Django Admin** (if not already added)
2. **Create test promotions** to see them on frontend
3. **Optionally create PromotionsPage** in admin frontend for easier management
4. **Consider adding Marketing Manager role** if you want dedicated promotion managers







