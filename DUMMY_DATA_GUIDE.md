# Dummy Data Generation Guide

## Overview
The `generate_dummy_data` management command creates comprehensive dummy data for **ALL** database tables in your Shwari Django project.

## Usage

### Basic Usage
```bash
# Activate virtual environment first
source venv/bin/activate

# Generate dummy data with default settings
python manage.py generate_dummy_data
```

### Clear Existing Data First
```bash
# Clear all existing data and generate fresh dummy data
python manage.py generate_dummy_data --clear
```

### Customize Amounts
```bash
# Generate more data
python manage.py generate_dummy_data \
  --products 50 \
  --units-per-product 10 \
  --reviews 150 \
  --orders 50 \
  --leads 60 \
  --promotions 20
```

## What Gets Created

### Core Data
- ✅ **Users** - Admin and Customer users
- ✅ **AdminRoles** - All role types (Salesperson, Inventory Manager, etc.)
- ✅ **Admins** - Multiple admins with different roles
- ✅ **Customers** - 25 customer accounts
- ✅ **Brands** - 3 brands (Affordable Gadgets, Premium, Budget)
- ✅ **Colors** - 11 color options
- ✅ **Tags** - 7 product tags
- ✅ **UnitAcquisitionSources** - Supplier/Import sources

### Products & Inventory
- ✅ **Products** - 30 products (default) with full details:
  - Product types (Phone, Laptop, Tablet, Accessory)
  - SEO fields (meta title, description, keywords, slug)
  - Product highlights and long descriptions
  - Product video URLs
  - Tags and brand associations
- ✅ **InventoryUnits** - 8 units per product (default) with:
  - Various conditions (New, Refurbished, Pre-owned)
  - Grades (A, B)
  - Storage, RAM, Battery specs
  - Processor details (for laptops)
  - Colors, prices, serial numbers, IMEIs
  - Different sale statuses
- ✅ **ProductAccessories** - Links accessories to main products

### Reviews & Content
- ✅ **Reviews** - 80 reviews (default) with:
  - Ratings (1-5 stars)
  - Comments
  - Optional video URLs
  - Customer and admin reviews

### Promotions
- ✅ **PromotionTypes** - Special Offer, Flash Sale, etc.
- ✅ **Promotions** - 10 promotions (default) with:
  - Discount percentages or amounts
  - Start/end dates
  - Product targeting
  - Display locations

### Requests & Transfers
- ✅ **ReservationRequests** - 20 requests (default) with various statuses
- ✅ **ReturnRequests** - 15 requests (default)
- ✅ **UnitTransfers** - 15 transfers (default) between salespersons

### Orders & E-commerce
- ✅ **Orders** - 25 orders (default) with:
  - Different statuses (Pending, Paid, Delivered, Canceled)
  - Walk-in and Online sources
  - Customer associations
- ✅ **OrderItems** - Items in each order
- ✅ **Leads** - 30 leads (default) with:
  - Various statuses (New, Contacted, Converted, Closed, Expired)
  - Customer information
  - Assigned salespersons
- ✅ **LeadItems** - Items in each lead
- ✅ **Carts** - 20 shopping carts (default)
- ✅ **CartItems** - Items in each cart with promotions

### Notifications & Logging
- ✅ **Notifications** - 50 notifications (default) for various events
- ✅ **AuditLogs** - 100 audit log entries (default) tracking system actions

## Default Quantities

| Item | Default Count |
|------|--------------|
| Products | 30 |
| Units per Product | 8 |
| Reviews | 80 |
| Reservation Requests | 20 |
| Return Requests | 15 |
| Unit Transfers | 15 |
| Orders | 25 |
| Leads | 30 |
| Carts | 20 |
| Promotions | 10 |
| Notifications | 50 |
| Audit Logs | 100 |

## Command Options

```
--products N              Number of products (default: 30)
--units-per-product N     Units per product (default: 8)
--reviews N               Number of reviews (default: 80)
--reservations N          Reservation requests (default: 20)
--returns N               Return requests (default: 15)
--transfers N             Unit transfers (default: 15)
--orders N                Orders (default: 25)
--leads N                 Leads (default: 30)
--carts N                 Shopping carts (default: 20)
--promotions N            Promotions (default: 10)
--notifications N         Notifications (default: 50)
--audit-logs N            Audit logs (default: 100)
--clear                   Clear existing data first
```

## Example Commands

### Quick Start (Default Settings)
```bash
python manage.py generate_dummy_data
```

### Large Dataset for Testing
```bash
python manage.py generate_dummy_data \
  --products 100 \
  --units-per-product 15 \
  --reviews 300 \
  --orders 100 \
  --leads 150 \
  --clear
```

### Minimal Dataset
```bash
python manage.py generate_dummy_data \
  --products 10 \
  --units-per-product 3 \
  --reviews 20 \
  --orders 5 \
  --leads 10
```

## Notes

1. **Image Files**: 
   - Product images and unit images are skipped because they require actual image files. In production, you'd want to download and save actual images.
   - **Promotion Banner Images**: The command now automatically downloads placeholder banner images for promotions that have `'stories_carousel'` in their `display_locations`. This requires the `requests` library (included in requirements.txt).

2. **Relationships**: All relationships are properly maintained:
   - Products linked to brands and tags
   - Units linked to products, colors, and sources
   - Orders linked to customers and units
   - Requests linked to admins and units
   - And more...

3. **Realistic Data**: The command generates realistic:
   - Product names and descriptions
   - Prices based on conditions
   - Dates spread over the past 90 days
   - Various statuses and states

4. **Safe to Run Multiple Times**: The command can be run multiple times, but use `--clear` if you want to start fresh.

## After Generation

After running the command, you'll see a summary showing counts for all created data. You can then:

1. **View in Admin Panel**: Access Django admin to see all the data
2. **Test Frontend**: Use the frontend to see products, reviews, etc.
3. **Test API**: All data is available through the REST API
4. **Test Features**: Reservation requests, transfers, orders, etc. are all ready to test

## Troubleshooting

If you encounter errors:
1. Make sure migrations are up to date: `python manage.py migrate`
2. Ensure you have required roles: Run `python manage.py migrate` to create default roles
3. Check that brands exist: Run `python manage.py create_default_brand` if needed

