# Brand Association Guide

## Overview

The system supports **multi-brand architecture** where:
- **Company Brands** = Different e-commerce sites (e.g., "Affordable Gadgets", "Brand B", "Brand C")
- **Product Brands** = Manufacturer brands (e.g., "Apple", "Samsung") - different concept
- Admins can be assigned to one or more company brands
- Products/Inventory can be associated with specific brands or be global

---

## How Brand Association Works

### 1. **Database Structure**

#### Brand Model (`inventory/models.py`)
```python
class Brand(models.Model):
    code = models.CharField(max_length=20, unique=True)  # e.g., "AFFORDABLE_GADGETS"
    name = models.CharField(max_length=100)               # e.g., "Affordable Gadgets"
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    logo = models.ImageField(...)
    primary_color = models.CharField(...)
    ecommerce_domain = models.CharField(...)  # e.g., "shwariphones.com"
```

#### Admin Model (`inventory/models.py`)
```python
class Admin(models.Model):
    user = models.OneToOneField(User, ...)
    brands = models.ManyToManyField('Brand', ...)  # Multiple brands per admin
    is_global_admin = models.BooleanField(default=False)  # Access to all brands
```

### 2. **How It Works**

#### **Step 1: Create a Brand**
- Brands are created via the admin interface or API
- Each brand has a unique `code` (e.g., `AFFORDABLE_GADGETS`, `BRAND_B`)
- Brand `code` is used in API requests via `X-Brand-Code` header

#### **Step 2: Assign Brands to Admins**
- Superusers can assign brands to any admin
- Admins can be assigned to:
  - **Specific brands** (e.g., only "Affordable Gadgets")
  - **Multiple brands** (e.g., "Affordable Gadgets" + "Brand B")
  - **All brands** (set `is_global_admin = True`)

#### **Step 3: Automatic Filtering**
- When an admin logs in, the system checks `admin.brands`
- All API queries are automatically filtered by admin's brands
- Admins only see/manage data for their assigned brands

---

## Setting Up a New Brand

### Method 1: Via Admin Interface (Recommended)

1. **Login as Superuser** to the admin interface
2. **Navigate to Brands page** (if available) or use Django admin
3. **Create new brand** with:
   - `code`: Unique identifier (e.g., `BRAND_B`)
   - `name`: Display name (e.g., "Brand B")
   - `is_active`: `True`
   - `ecommerce_domain`: Domain for the brand's site (optional)

### Method 2: Via API

```bash
POST /api/inventory/brands/
Headers: Authorization: Token <superuser_token>
Body:
{
  "code": "BRAND_B",
  "name": "Brand B",
  "description": "Second brand e-commerce site",
  "is_active": true,
  "ecommerce_domain": "brandb.com"
}
```

### Method 3: Via Django Admin

1. Go to `http://localhost:8000/admin/`
2. Navigate to **Inventory → Brands**
3. Click **Add Brand**
4. Fill in the form and save

### Method 4: Via Django Shell

```python
python manage.py shell
>>> from inventory.models import Brand
>>> Brand.objects.create(
...     code="BRAND_B",
...     name="Brand B",
...     description="Second brand",
...     is_active=True,
...     ecommerce_domain="brandb.com"
... )
```

---

## Connecting Brand to Admin Interface

### Step-by-Step Process

#### **Step 1: Create the Brand** (see above)

#### **Step 2: Assign Brand to Admin**

**Via Admin Interface:**
1. Login as **Superuser**
2. Go to **Admins** page (`/admins`)
3. Find the admin user you want to assign brands to
4. Click **"Brands"** button on their card
5. In the modal:
   - Check/uncheck brands to assign
   - Or check "Global Admin" for access to all brands
6. Click **"Assign Brands"**

**Via API:**
```bash
POST /api/inventory/admins/{admin_id}/brands/
Headers: Authorization: Token <superuser_token>
Body:
{
  "brand_ids": [1, 2],  # IDs of brands to assign
  "is_global_admin": false
}
```

**Via Django Shell:**
```python
python manage.py shell
>>> from inventory.models import Admin, Brand
>>> admin = Admin.objects.get(user__username="fabian")
>>> brand = Brand.objects.get(code="BRAND_B")
>>> admin.brands.add(brand)
>>> admin.save()
```

#### **Step 3: Verify Assignment**

- Admin logs in
- Admin sees brand selector (if multiple brands) or brand badge (if single brand)
- All data is filtered by assigned brands

---

## How Filtering Works

### Automatic Filtering in ViewSets

All admin ViewSets automatically filter by `admin.brands`:

```python
# Example from ProductViewSet
def get_queryset(self):
    queryset = super().get_queryset()
    user = self.request.user
    
    if user.is_superuser:
        return queryset  # Superuser sees all
    
    try:
        admin = Admin.objects.get(user=user)
        if admin.is_global_admin:
            return queryset  # Global admin sees all
        
        # Filter by admin's brands
        if admin.brands.exists():
            queryset = queryset.filter(
                Q(brands__in=admin.brands.all()) | 
                Q(brands__isnull=True) | 
                Q(is_global=True)
            ).distinct()
        else:
            return queryset.none()  # No brands = see nothing
    except Admin.DoesNotExist:
        return queryset.none()
    
    return queryset
```

### What Gets Filtered

- **Products**: Only products associated with admin's brands (or global products)
- **Inventory Units**: Only units associated with admin's brands (or global units)
- **Orders**: Only orders containing items from admin's brands
- **Leads**: Only leads for admin's brands
- **Promotions**: Only promotions for admin's brands

---

## Complete Setup Example

### Scenario: Setting up "Brand B"

1. **Create Brand:**
   ```python
   Brand.objects.create(
       code="BRAND_B",
       name="Brand B",
       is_active=True,
       ecommerce_domain="brandb.com"
   )
   ```

2. **Create Admin User** (if not exists):
   ```python
   from django.contrib.auth import get_user_model
   User = get_user_model()
   user = User.objects.create_user(
       username="brandb_admin",
       email="admin@brandb.com",
       password="secure_password",
       is_staff=True
   )
   ```

3. **Create Admin Profile:**
   ```python
   from inventory.models import Admin, AdminRole
   admin = Admin.objects.create(
       user=user,
       admin_code="BRAND_B_ADMIN"
   )
   # Assign roles
   salesperson_role = AdminRole.objects.get(name="SP")
   admin.roles.add(salesperson_role)
   ```

4. **Assign Brand to Admin:**
   ```python
   brand_b = Brand.objects.get(code="BRAND_B")
   admin.brands.add(brand_b)
   admin.save()
   ```

5. **Create E-commerce Frontend:**
   - Create new Next.js app in `frontend_inventory_and_orders/brand-b/`
   - Set `NEXT_PUBLIC_BRAND_CODE=BRAND_B` in `.env.local`
   - Frontend will automatically send `X-Brand-Code: BRAND_B` header

---

## Frontend Connection

### For E-commerce Sites

Each brand's frontend automatically includes the brand code:

```typescript
// frontend_inventory_and_orders/brand-b/lib/config/brand.ts
export const brandConfig = {
  code: 'BRAND_B',  // Matches Brand.code in database
  name: 'Brand B',
  apiBaseUrl: 'http://localhost:8000',
}
```

The API client automatically adds the header:
```typescript
headers: {
  'X-Brand-Code': brandConfig.code,  // Sent with every request
}
```

### For Admin Interface

- Admins see a **brand selector** if they have multiple brands
- Selected brand is saved in `localStorage`
- All API calls are filtered by admin's brands automatically (no header needed)

---

## Key Points

1. **Brand Code Must Match**: The `code` field in the Brand model must match what the frontend sends in `X-Brand-Code` header

2. **Global Products**: Products with `is_global=True` or no brand assignment are visible to all admins

3. **Global Admins**: Admins with `is_global_admin=True` see all brands regardless of assignment

4. **Superusers**: Always see everything (bypass all filters)

5. **Brand Assignment**: Only superusers can assign brands to admins (via `/admins/{id}/brands/` endpoint)

---

## Troubleshooting

### Admin can't see any data
- Check: `admin.brands.exists()` - admin must have at least one brand assigned
- Check: Brands are `is_active=True`

### Frontend can't connect to backend
- Check: Brand code matches between frontend config and database
- Check: Backend is running on `0.0.0.0:8000` (not just `127.0.0.1:8000`)
- Check: CORS includes the frontend origin

### Admin sees wrong brand's data
- Check: Brand assignment in admin profile
- Check: `is_global_admin` flag
- Check: ViewSet filtering logic

---

## API Endpoints

### Brand Management
- `GET /api/inventory/brands/` - List brands (filtered by admin's brands)
- `POST /api/inventory/brands/` - Create brand (superuser only)
- `GET /api/inventory/brands/{id}/` - Get brand details
- `PUT/PATCH /api/inventory/brands/{id}/` - Update brand

### Admin Brand Assignment
- `POST /api/inventory/admins/{id}/brands/` - Assign brands to admin
- `PUT /api/inventory/admins/{id}/brands/` - Update brand assignment

---

## Summary

1. **Create Brand** → Database entry with unique `code`
2. **Assign to Admin** → Link admin to brand(s) via ManyToMany
3. **Automatic Filtering** → All queries filtered by `admin.brands`
4. **Frontend Connection** → Frontend sends `X-Brand-Code` header
5. **E-commerce Site** → Each brand has its own Next.js frontend

The system handles all filtering automatically - you just need to:
- Create the brand
- Assign it to admins
- Configure the frontend with the matching brand code







