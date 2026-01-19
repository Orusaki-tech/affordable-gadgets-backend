# API Endpoints Reference

Complete reference of all API endpoints in the Affordable Gadgets Platform.

---

## Table of Contents

1. [Public API Endpoints](#public-api-endpoints)
2. [Admin API Endpoints](#admin-api-endpoints)
3. [Authentication Endpoints](#authentication-endpoints)
4. [API Request/Response Formats](#api-requestresponse-formats)
5. [Error Handling](#error-handling)

---

## Base URLs

- **Backend API**: `https://your-api-domain.com`
- **Public API**: `/api/v1/public/`
- **Admin API**: `/api/inventory/`
- **API Documentation**: `/api/schema/swagger-ui/`

---

## Public API Endpoints

Base path: `/api/v1/public/`

### Products

#### List Products
```
GET /api/v1/public/products/
```

**Query Parameters:**
- `search`: Search term
- `product_type`: Filter by type (PH, LT, TB, AC)
- `brand`: Filter by brand code
- `min_price`: Minimum price filter
- `max_price`: Maximum price filter
- `page`: Page number
- `page_size`: Items per page

**Response:**
```json
{
  "count": 100,
  "next": "http://api.example.com/api/v1/public/products/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "product_name": "iPhone 15 Pro",
      "slug": "iphone-15-pro",
      "product_type": "PH",
      "brand": "Apple",
      "min_price": 999.00,
      "max_price": 1299.00,
      "available_units_count": 5,
      "primary_image": "https://cloudinary.com/image.jpg",
      "rating": 4.5,
      "review_count": 25
    }
  ]
}
```

#### Get Product Details
```
GET /api/v1/public/products/{id}/
```

**Response:**
```json
{
  "id": 1,
  "product_name": "iPhone 15 Pro",
  "slug": "iphone-15-pro",
  "product_description": "Latest iPhone model...",
  "product_type": "PH",
  "brand": "Apple",
  "model_series": "iPhone 15",
  "specifications": {
    "storage": "256GB",
    "color": "Natural Titanium",
    "ram": "8GB"
  },
  "images": [
    {
      "id": 1,
      "image_url": "https://cloudinary.com/image1.jpg",
      "is_primary": true
    }
  ],
  "available_units": [
    {
      "id": 101,
      "price": 999.00,
      "condition": "NEW",
      "storage": "256GB",
      "color": "Natural Titanium"
    }
  ],
  "reviews": [...],
  "accessories": [...]
}
```

### Cart Operations

#### Get Cart
```
GET /api/v1/public/cart/
```

**Headers:**
- `X-Brand-Code`: Required (e.g., "AFFORDABLE_GADGETS")
- `X-Session-Key`: Optional (for session-based carts)
- `X-Customer-Phone`: Optional (for phone-based carts)

**Response:**
```json
{
  "id": 1,
  "session_key": "abc123",
  "customer_phone": "+1234567890",
  "items": [
    {
      "id": 1,
      "unit": {
        "id": 101,
        "product": {
          "id": 1,
          "product_name": "iPhone 15 Pro"
        },
        "price": 999.00
      },
      "quantity": 1
    }
  ],
  "total_amount": 999.00,
  "item_count": 1
}
```

#### Add to Cart
```
POST /api/v1/public/cart/
```

**Request Body:**
```json
{
  "unit_id": 101,
  "quantity": 1
}
```

**Headers:**
- `X-Brand-Code`: Required
- `X-Session-Key`: Optional
- `X-Customer-Phone`: Optional

**Response:**
```json
{
  "id": 1,
  "items": [...],
  "total_amount": 999.00,
  "message": "Item added to cart"
}
```

#### Update Cart Item
```
PATCH /api/v1/public/cart/{cart_id}/
```

**Request Body:**
```json
{
  "item_id": 1,
  "quantity": 2
}
```

#### Remove from Cart
```
DELETE /api/v1/public/cart/{cart_id}/items/{item_id}/
```

### Promotions

#### List Promotions
```
GET /api/v1/public/promotions/
```

**Query Parameters:**
- `is_active`: Filter active promotions (true/false)
- `promotion_type`: Filter by type

**Response:**
```json
{
  "count": 5,
  "results": [
    {
      "id": 1,
      "title": "Summer Sale",
      "description": "Up to 50% off",
      "promotion_type": "DISCOUNT",
      "banner_image": "https://cloudinary.com/banner.jpg",
      "start_date": "2024-01-01T00:00:00Z",
      "end_date": "2024-12-31T23:59:59Z",
      "is_active": true
    }
  ]
}
```

### Reviews

#### List Reviews
```
GET /api/v1/public/reviews/
```

**Query Parameters:**
- `product`: Filter by product ID
- `rating`: Filter by rating (1-5)
- `page`: Page number

**Response:**
```json
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "product": 1,
      "customer_name": "John Doe",
      "rating": 5,
      "comment": "Great product!",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Budget Search

#### Search Products by Budget
```
POST /api/v1/public/phone-search/
```

**Request Body:**
```json
{
  "min_budget": 500,
  "max_budget": 1000,
  "product_type": "PH"
}
```

**Response:**
```json
{
  "results": [
    {
      "unit_id": 101,
      "product": {
        "id": 1,
        "product_name": "iPhone 15 Pro"
      },
      "price": 999.00,
      "match_score": 95
    }
  ],
  "total_matches": 10
}
```

---

## Admin API Endpoints

Base path: `/api/inventory/`

**Authentication Required**: Token Authentication
**Header**: `Authorization: Token <your-token>`

### Authentication

#### Admin Login
```
POST /api/auth/token/login/
```

**Request Body:**
```json
{
  "username": "admin",
  "password": "password"
}
```

**Response:**
```json
{
  "auth_token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com"
  }
}
```

### Products Management

#### List Products (Admin)
```
GET /api/inventory/products/
```

**Query Parameters:**
- `brand`: Filter by brand ID
- `product_type`: Filter by type
- `search`: Search term
- `page`: Page number

#### Create Product
```
POST /api/inventory/products/
```

**Request Body:**
```json
{
  "product_name": "iPhone 15 Pro",
  "product_type": "PH",
  "brand": "Apple",
  "model_series": "iPhone 15",
  "product_description": "Latest iPhone model",
  "specifications": {
    "storage": "256GB",
    "ram": "8GB"
  }
}
```

#### Update Product
```
PATCH /api/inventory/products/{id}/
```

#### Delete Product
```
DELETE /api/inventory/products/{id}/
```

### Inventory Units

#### List Units
```
GET /api/inventory/units/
```

**Query Parameters:**
- `product`: Filter by product ID
- `status`: Filter by status (AVAILABLE, RESERVED, SOLD, etc.)
- `sale_status`: Filter by sale status
- `brand`: Filter by brand ID

#### Create Unit
```
POST /api/inventory/units/
```

**Request Body:**
```json
{
  "product": 1,
  "price": 999.00,
  "condition": "NEW",
  "status": "AVAILABLE",
  "storage": "256GB",
  "color": "Natural Titanium",
  "imei": "123456789012345"
}
```

#### Update Unit
```
PATCH /api/inventory/units/{id}/
```

#### Bulk Update Units
```
PATCH /api/inventory/units/bulk_update/
```

**Request Body:**
```json
{
  "unit_ids": [1, 2, 3],
  "updates": {
    "status": "AVAILABLE",
    "price": 899.00
  }
}
```

### Orders Management

#### List Orders
```
GET /api/inventory/orders/
```

**Query Parameters:**
- `status`: Filter by status (PENDING, PAID, DELIVERED, etc.)
- `customer`: Filter by customer ID
- `brand`: Filter by brand ID
- `date_from`: Filter from date
- `date_to`: Filter to date

**Response:**
```json
{
  "count": 100,
  "results": [
    {
      "order_id": "550e8400-e29b-41d4-a716-446655440000",
      "customer": {
        "id": 1,
        "name": "John Doe",
        "phone": "+1234567890"
      },
      "status": "PAID",
      "total_amount": 999.00,
      "created_at": "2024-01-15T10:30:00Z",
      "items": [
        {
          "id": 1,
          "unit": {
            "id": 101,
            "product": {
              "product_name": "iPhone 15 Pro"
            }
          },
          "quantity": 1,
          "price": 999.00
        }
      ]
    }
  ]
}
```

#### Get Order Details
```
GET /api/inventory/orders/{order_id}/
```

#### Create Order
```
POST /api/inventory/orders/
```

**Request Body:**
```json
{
  "customer_phone": "+1234567890",
  "customer_name": "John Doe",
  "items": [
    {
      "unit_id": 101,
      "quantity": 1
    }
  ],
  "delivery_address": "123 Main St",
  "notes": "Handle with care"
}
```

#### Initiate Payment
```
POST /api/inventory/orders/{order_id}/initiate_payment/
```

**Request Body:**
```json
{
  "callback_url": "https://frontend.com/payment/callback",
  "cancellation_url": "https://frontend.com/payment/cancelled"
}
```

**Response:**
```json
{
  "success": true,
  "redirect_url": "https://pesapal.com/payment/...",
  "order_tracking_id": "abc123xyz"
}
```

#### Confirm Payment
```
POST /api/inventory/orders/{order_id}/confirm_payment/
```

**Response:**
```json
{
  "success": true,
  "message": "Payment confirmed. 1 unit(s) marked as SOLD."
}
```

#### Get Payment Status
```
GET /api/inventory/orders/{order_id}/payment_status/
```

#### Generate Receipt
```
GET /api/inventory/orders/{order_id}/receipt/
```

**Response:** PDF file download

### Leads Management

#### List Leads
```
GET /api/inventory/leads/
```

**Query Parameters:**
- `status`: Filter by status (PENDING, CONTACTED, CONVERTED, REJECTED)
- `brand`: Filter by brand ID
- `date_from`: Filter from date

#### Get Lead Details
```
GET /api/inventory/leads/{id}/
```

#### Convert Lead to Order
```
POST /api/inventory/leads/{id}/convert/
```

**Request Body:**
```json
{
  "salesperson_id": 1,
  "notes": "Customer confirmed order"
}
```

### Promotions Management

#### List Promotions
```
GET /api/inventory/promotions/
```

#### Create Promotion
```
POST /api/inventory/promotions/
```

**Request Body (multipart/form-data):**
```
title: Summer Sale
description: Up to 50% off
promotion_type: DISCOUNT
start_date: 2024-01-01T00:00:00Z
end_date: 2024-12-31T23:59:59Z
banner_image: <file>
is_active: true
```

### Reports

#### Generate Report
```
GET /api/inventory/reports/
```

**Query Parameters:**
- `report_type`: Type of report (sales, inventory, customers)
- `date_from`: Start date
- `date_to`: End date
- `brand`: Filter by brand ID
- `format`: Output format (json, csv, excel)

### Stock Alerts

#### Get Stock Alerts
```
GET /api/inventory/stock-alerts/
```

**Response:**
```json
{
  "low_stock": [
    {
      "product_id": 1,
      "product_name": "iPhone 15 Pro",
      "available_count": 2,
      "threshold": 5
    }
  ],
  "out_of_stock": [...],
  "overstock": [...]
}
```

---

## API Request/Response Formats

### Request Headers

**Public API:**
```
X-Brand-Code: AFFORDABLE_GADGETS
X-Session-Key: abc123 (optional)
X-Customer-Phone: +1234567890 (optional)
Content-Type: application/json
```

**Admin API:**
```
Authorization: Token <your-token>
Content-Type: application/json
```

### Response Format

**Success Response:**
```json
{
  "id": 1,
  "field1": "value1",
  "field2": "value2"
}
```

**List Response:**
```json
{
  "count": 100,
  "next": "http://api.example.com/endpoint/?page=2",
  "previous": null,
  "results": [...]
}
```

**Error Response:**
```json
{
  "error": "Error message",
  "detail": "Detailed error description",
  "field_errors": {
    "field_name": ["Error message"]
  }
}
```

---

## Error Handling

### HTTP Status Codes

- `200 OK`: Successful request
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### Common Error Responses

#### Validation Error (400)
```json
{
  "field_name": ["This field is required."]
}
```

#### Authentication Error (401)
```json
{
  "detail": "Authentication credentials were not provided."
}
```

#### Permission Error (403)
```json
{
  "detail": "You do not have permission to perform this action."
}
```

#### Not Found (404)
```json
{
  "detail": "Not found."
}
```

---

## Rate Limiting

- Public API: 100 requests per minute per IP
- Admin API: 1000 requests per minute per token

---

## API Versioning

Current version: `v1`

API versioning is handled via URL path:
- `/api/v1/public/` - Public API v1
- `/api/inventory/` - Admin API (current version)

---

## Interactive API Documentation

Access interactive API documentation at:
- **Swagger UI**: `/api/schema/swagger-ui/`
- **ReDoc**: `/api/schema/redoc/`
- **OpenAPI Schema**: `/api/schema/`

---

*Last Updated: $(date)*
*API Version: 1.0.0*
