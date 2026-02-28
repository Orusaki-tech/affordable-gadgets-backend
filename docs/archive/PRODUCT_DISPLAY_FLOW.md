# Product Display Flow: Backend to Frontend

This document explains how products are displayed in the `affordable-gadgets-frontend` from the `affordable-gadgets-backend`.

## Overview

The flow follows this path:
1. **Frontend Component** → 2. **React Query Hook** → 3. **API Client** → 4. **Backend ViewSet** → 5. **Serializer** → 6. **Database**

---

## 1. Frontend: User Interface Layer

### Entry Point: Products Page
**File:** `affordable-gadgets-frontend/app/products/page.tsx`

- Next.js page component that renders the `ProductsPage` component
- Wraps it with `Header` and `Footer` components
- Uses React Suspense for loading states

### Main Component: ProductsPage
**File:** `affordable-gadgets-frontend/components/ProductsPage.tsx`

**Key Features:**
- Manages search, filters, pagination, and sorting state
- Reads URL query parameters (e.g., `?promotion=123`, `?search=iphone`)
- Uses the `useProducts` hook to fetch data
- Renders `ProductCard` components in a grid layout
- Handles pagination controls

**State Management:**
```typescript
- page: Current page number
- search: Search query string
- filters: { type, minPrice, maxPrice, brand }
- sort: Ordering parameter
```

**API Call:**
```typescript
const { data, isLoading, error } = useProducts({
  page,
  page_size: 24,
  type: filters.type,
  search: search,
  brand_filter: filters.brand,
  min_price: filters.minPrice,
  max_price: filters.maxPrice,
  ordering: sort,
  promotion: promotionId
});
```

### Product Card Component
**File:** `affordable-gadgets-frontend/components/ProductCard.tsx`

**Displays:**
- Product image (primary image or placeholder)
- Product name, brand, model series
- Price range (min_price - max_price)
- Stock status and available units count
- Interest count badge
- Tags (first 2 tags)
- Link to product detail page (`/products/{slug}`)

---

## 2. Frontend: Data Fetching Layer

### React Query Hook
**File:** `affordable-gadgets-frontend/lib/hooks/useProducts.ts`

**Purpose:** Provides React Query hooks for product data fetching

**Hooks:**
1. **`useProducts(params)`** - Fetches paginated list of products
   - Uses `productsApi.getProducts(params)`
   - Query key: `['products', params]`
   - Stale time: 30 seconds

2. **`useProduct(id)`** - Fetches single product by ID
   - Uses `productsApi.getProduct(id)`
   - Query key: `['product', id]`

3. **`useProductBySlug(slug)`** - Fetches product by slug
   - Uses `productsApi.getProductBySlug(slug)`
   - Query key: `['product', 'slug', slug]`

4. **`useProductUnits(productId)`** - Fetches available units for a product
   - Uses `productsApi.getProductUnits(productId)`
   - Query key: `['product', productId, 'units']`
   - Stale time: 10 seconds (more frequent updates for stock)

### API Client Functions
**File:** `affordable-gadgets-frontend/lib/api/products.ts`

**Functions:**
1. **`getProducts(params)`**
   - Makes GET request to `/products/`
   - Supports query parameters: `page`, `page_size`, `type`, `search`, `brand_filter`, `min_price`, `max_price`, `ordering`, `promotion`
   - Returns `PaginatedResponse<Product>`

2. **`getProduct(id)`**
   - Makes GET request to `/products/{id}/`
   - Returns single `Product`

3. **`getProductBySlug(slug)`**
   - Tries multiple strategies:
     - If slug is numeric, tries ID lookup first
     - Then tries exact slug filter: `/products/?slug={slug}`
     - Falls back to searching all products and matching by slug
   - Returns single `Product`

4. **`getProductUnits(productId)`**
   - Makes GET request to `/products/{productId}/units/`
   - Returns array of `InventoryUnit[]`

### API Client Configuration
**File:** `affordable-gadgets-frontend/lib/api/client.ts`

**Key Features:**
- Base URL: `{apiBaseUrl}/api/v1/public`
- Automatically includes `X-Brand-Code` header from brand config
- Uses axios with interceptors for error handling
- Supports credentials (cookies) for session management

**Brand Configuration:**
- Reads from `brandConfig` (environment variables)
- Default: `AFFORDABLE_GADGETS`
- Header: `X-Brand-Code: {brandCode}`

---

## 3. Backend: API Routing Layer

### URL Configuration
**File:** `affordable-gadgets-backend/store/urls.py`

**Route:**
```python
path('api/v1/public/', include('inventory.urls_public'))
```

### Public API URLs
**File:** `affordable-gadgets-backend/inventory/urls_public.py`

**Routes:**
- `GET /api/v1/public/products/` → `PublicProductViewSet.list()`
- `GET /api/v1/public/products/{id}/` → `PublicProductViewSet.retrieve()`
- `GET /api/v1/public/products/{id}/units/` → `PublicProductViewSet.units()`
- `GET /api/v1/public/phone-search/` → `PhoneSearchByBudgetView`

**Router Registration:**
```python
router.register(r'products', views_public.PublicProductViewSet, basename='public-product')
```

---

## 4. Backend: Middleware Layer

### Brand Context Middleware
**File:** `affordable-gadgets-backend/inventory/middleware.py`

**Purpose:** Extracts brand from `X-Brand-Code` header and attaches to request

**Process:**
1. Reads `X-Brand-Code` header from request
2. Looks up `Brand` model by code (must be active)
3. Sets `request.brand` attribute
4. If brand not found or inactive, `request.brand = None`

**Usage in Views:**
- Views can access `request.brand` to filter products by brand
- Products can be brand-specific, global, or brandless

---

## 5. Backend: ViewSet Layer

### PublicProductViewSet
**File:** `affordable-gadgets-backend/inventory/views_public.py`

**Class:** `PublicProductViewSet(viewsets.ReadOnlyModelViewSet)`

**Base Queryset:**
```python
queryset = Product.objects.filter(is_discontinued=False, is_published=True)
```

### Key Methods:

#### `get_queryset()`
**Purpose:** Builds optimized queryset with filtering, annotations, and prefetching

**Process Flow:**

1. **Slug Lookup (Special Case)**
   - If `slug` query param exists, returns single product
   - Bypasses brand filtering for slug-based access

2. **Base Filtering**
   - Starts with published, non-discontinued products
   - Gets brand from `request.brand`

3. **Inventory Unit Filtering**
   - Filters units by: `sale_status=AVAILABLE`, `available_online=True`
   - If brand exists, filters units: `(brands=brand OR brands__isnull=True)`

4. **Prefetching (Performance Optimization)**
   - Prefetches available inventory units
   - Prefetches primary product images
   - Reduces N+1 query problems

5. **Annotations (Aggregated Data)**
   - `available_units_count`: 
     - For accessories: Sum of `quantity` field
     - For phones/laptops/tablets: Count of distinct units
   - `min_price`: Minimum `selling_price` from available units
   - `max_price`: Maximum `selling_price` from available units
   - `brand_count`: Count of associated brands

6. **Brand Filtering**
   - If brand exists: `(brands=brand OR is_global=True OR brand_count=0)`
   - If no brand: Shows all published products

7. **Additional Filters**
   - `type`: Filter by product type (PH, LT, TB, AC)
   - `brand_filter`: Filter by brand name (contains)
   - `min_price`/`max_price`: Filter by price range
   - `promotion`: Filter by promotion ID (must be active and within date range)

8. **Search**
   - Uses DRF SearchFilter on: `product_name`, `brand`, `product_description`

9. **Ordering**
   - Default: `-available_units_count`, `product_name`
   - Can be overridden with `ordering` query param
   - Valid fields: `product_name`, `min_price`, `max_price`, `available_units_count`

10. **Pagination**
    - Handled by DRF's pagination (default page size: 24)

#### `list(request)`
**Purpose:** Handles GET `/products/` requests

- Calls `get_queryset()` to build filtered queryset
- Applies pagination
- Returns serialized data via `PublicProductSerializer`
- Includes error handling and logging

#### `units(request, pk)`
**Purpose:** Handles GET `/products/{id}/units/` requests

- Returns available inventory units for a product
- Filters by brand if provided
- Includes interest count for each unit
- Serialized via `PublicInventoryUnitSerializer`

---

## 6. Backend: Serialization Layer

### PublicProductSerializer
**File:** `affordable-gadgets-backend/inventory/serializers_public.py`

**Purpose:** Converts Product model instances to JSON

**Fields Serialized:**
- `id`, `product_name`, `brand`, `model_series`, `product_type`
- `product_description`, `long_description`, `product_highlights`
- `available_units_count` (computed)
- `interest_count` (computed)
- `min_price`, `max_price` (computed)
- `primary_image` (computed, optimized URL)
- `slug`, `product_video_url`
- `tags` (array of tag names)

**Key Methods:**

#### `get_available_units_count(obj)`
- Uses annotation from queryset if available (optimized)
- Falls back to querying inventory units
- For accessories: Sums `quantity`
- For other types: Counts distinct units

#### `get_interest_count(obj)`
- Counts active leads (NEW, CONTACTED status) for product's units
- Uses prefetched units if available
- Filters by brand if provided

#### `get_min_price(obj)` / `get_max_price(obj)`
- Uses annotation from queryset if available
- Falls back to querying unit prices
- Returns `float` or `None`

#### `get_primary_image(obj)`
- Uses prefetched primary images if available
- Builds absolute URLs for local media
- Returns Cloudinary optimized URL if configured
- Falls back to local absolute URL

#### `get_tags(obj)`
- Returns list of tag names from many-to-many relationship

---

## 7. Database Layer

### Product Model
**File:** `affordable-gadgets-backend/inventory/models.py`

**Key Fields:**
- `product_name`, `brand`, `model_series`, `product_type`
- `product_description`, `long_description`, `product_highlights`
- `is_published`, `is_discontinued`
- `slug` (unique identifier for URLs)
- `product_video_url`
- Relationships: `brands` (many-to-many), `tags` (many-to-many), `images` (one-to-many), `inventory_units` (one-to-many)

### InventoryUnit Model
**Key Fields:**
- `product_template` (ForeignKey to Product)
- `selling_price`, `condition`, `grade`
- `storage_gb`, `ram_gb`, `battery_mah`
- `sale_status` (AVAILABLE, SOLD, RESERVED, etc.)
- `available_online` (boolean)
- `quantity` (for accessories)
- `brands` (many-to-many, for brand-specific units)

---

## Complete Request Flow Example

### Example: Loading Products Page

1. **User navigates to** `/products`

2. **Frontend (`ProductsPage.tsx`):**
   - Component mounts
   - Calls `useProducts({ page: 1, page_size: 24 })`

3. **React Query (`useProducts.ts`):**
   - Executes `productsApi.getProducts({ page: 1, page_size: 24 })`

4. **API Client (`products.ts`):**
   - Makes HTTP GET: `http://localhost:8000/api/v1/public/products/?page=1&page_size=24`
   - Includes header: `X-Brand-Code: AFFORDABLE_GADGETS`

5. **Backend Middleware (`middleware.py`):**
   - Reads `X-Brand-Code` header
   - Looks up Brand with code `AFFORDABLE_GADGETS`
   - Sets `request.brand = <Brand instance>`

6. **Backend ViewSet (`views_public.py`):**
   - `PublicProductViewSet.list()` called
   - `get_queryset()` builds queryset:
     - Base: `Product.objects.filter(is_discontinued=False, is_published=True)`
     - Prefetches available units and images
     - Annotates with `available_units_count`, `min_price`, `max_price`
     - Filters by brand: `(brands=brand OR is_global=True OR brand_count=0)`
     - Orders by: `-available_units_count`, `product_name`
   - Applies pagination (page 1, 24 items)
   - Serializes via `PublicProductSerializer`

7. **Backend Serializer (`serializers_public.py`):**
   - Converts each Product to JSON
   - Computes `available_units_count` from annotation
   - Computes `min_price`/`max_price` from annotation
   - Gets `primary_image` from prefetched images
   - Gets `tags` from many-to-many relationship
   - Computes `interest_count` from Lead model

8. **Response:**
   ```json
   {
     "count": 150,
     "next": "http://localhost:8000/api/v1/public/products/?page=2&page_size=24",
     "previous": null,
     "results": [
       {
         "id": 1,
         "product_name": "iPhone 15 Pro",
         "brand": "Apple",
         "model_series": "iPhone 15",
         "product_type": "PH",
         "available_units_count": 5,
         "min_price": 120000.00,
         "max_price": 150000.00,
         "primary_image": "https://cloudinary.com/...",
         "slug": "iphone-15-pro",
         "tags": ["new", "premium"],
         ...
       },
       ...
     ]
   }
   ```

9. **Frontend (`ProductsPage.tsx`):**
   - Receives data from React Query
   - Maps over `data.results`
   - Renders `ProductCard` for each product

10. **ProductCard Component:**
    - Displays product image, name, price range
    - Shows stock status and interest count
    - Creates link to `/products/iphone-15-pro`

---

## Key Features

### Performance Optimizations

1. **Prefetching:** Reduces N+1 queries by prefetching related data
2. **Annotations:** Computes aggregated data (counts, prices) in database
3. **Query Optimization:** Uses `select_related` and `prefetch_related`
4. **Caching:** React Query caches responses (30s stale time)

### Brand Filtering

- Products can be:
  - **Brand-specific:** Only shown for that brand
  - **Global:** Shown for all brands
  - **Brandless:** Shown when no brand is specified

### Product Types

- **PH** (Phone): Counts distinct units
- **LT** (Laptop): Counts distinct units
- **TB** (Tablet): Counts distinct units
- **AC** (Accessory): Sums `quantity` field

### Filtering Capabilities

- Search by name, brand, description
- Filter by product type
- Filter by price range
- Filter by brand name
- Filter by promotion
- Sort by name, price, stock count

---

## Error Handling

### Frontend
- React Query handles loading/error states
- API client interceptors log errors
- Components show error messages to users

### Backend
- ViewSet catches exceptions and returns 500 with error message
- Serializer validation errors return 400
- Missing products return 404

---

## Environment Configuration

### Frontend
- `NEXT_PUBLIC_BRAND_CODE`: Brand code (default: `AFFORDABLE_GADGETS`)
- `NEXT_PUBLIC_API_BASE_URL`: Backend URL (default: `http://localhost:8000`)

### Backend
- `DEBUG`: Enable debug mode
- Database settings for PostgreSQL
- Cloudinary settings for image optimization

---

## Summary

The product display flow is a well-architected system that:

1. **Separates concerns:** UI, data fetching, API, business logic, database
2. **Optimizes performance:** Prefetching, annotations, caching
3. **Supports multi-brand:** Brand filtering at middleware and viewset level
4. **Handles edge cases:** Slug lookups, promotions, search, filtering
5. **Provides good UX:** Loading states, error handling, pagination

The flow ensures products are efficiently queried, filtered, and displayed while maintaining good performance and user experience.
