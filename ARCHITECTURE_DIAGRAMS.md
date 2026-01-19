# Affordable Gadgets Platform - Architecture Diagrams

This document provides comprehensive service diagrams at multiple levels of detail, from high-level system context to detailed component interactions.

---

## Table of Contents

1. [Level 1: System Context Diagram](#level-1-system-context-diagram)
2. [Level 2: Container Diagram](#level-2-container-diagram)
3. [Level 3: Component Diagram - Backend](#level-3-component-diagram-backend)
4. [Level 4: Component Diagram - Frontend](#level-4-component-diagram-frontend)
5. [Database Schema Diagram](#database-schema-diagram)
6. [Service Interaction Diagrams](#service-interaction-diagrams)
7. [API Flow Diagrams](#api-flow-diagrams)

---

## Level 1: System Context Diagram

High-level view showing the system and its external dependencies.

```mermaid
graph TB
    subgraph "Affordable Gadgets Platform"
        Customer[Customer]
        Admin[Admin User]
        Ecommerce[E-commerce Frontend<br/>Next.js]
        AdminPanel[Admin Frontend<br/>React]
        Backend[Django Backend API]
        DB[(PostgreSQL<br/>Database)]
    end
    
    subgraph "External Services"
        Cloudinary[Cloudinary<br/>Image Storage]
        Pesapal[Pesapal<br/>Payment Gateway]
        Twilio[Twilio/WhatsApp<br/>Notifications]
    end
    
    Customer -->|Browse Products<br/>Place Orders| Ecommerce
    Admin -->|Manage Inventory<br/>Process Orders| AdminPanel
    Ecommerce -->|API Calls| Backend
    AdminPanel -->|API Calls| Backend
    Backend -->|Store Data| DB
    Backend -->|Upload Images| Cloudinary
    Backend -->|Process Payments| Pesapal
    Backend -->|Send Notifications| Twilio
    
    style Customer fill:#e1f5ff
    style Admin fill:#fff4e1
    style Ecommerce fill:#e8f5e9
    style AdminPanel fill:#e8f5e9
    style Backend fill:#f3e5f5
    style DB fill:#ffebee
    style Cloudinary fill:#fff9c4
    style Pesapal fill:#fff9c4
    style Twilio fill:#fff9c4
```

### Key Actors
- **Customer**: End users browsing and purchasing products
- **Admin User**: Staff managing inventory, orders, and content

### External Systems
- **Cloudinary**: Image and media storage/CDN
- **Pesapal**: Payment processing gateway
- **Twilio/WhatsApp**: SMS and WhatsApp notifications

---

## Level 2: Container Diagram

Shows the high-level technical building blocks and their responsibilities.

```mermaid
graph TB
    subgraph "Frontend Applications"
        Ecommerce[E-commerce Frontend<br/>Next.js 14<br/>Port: 3000]
        AdminPanel[Admin Frontend<br/>React CRA<br/>Port: 3000]
    end
    
    subgraph "Backend Services"
        API[Django REST API<br/>Django 5.2.7<br/>Port: 8000]
        AdminUI[Django Admin<br/>Built-in Admin]
    end
    
    subgraph "Data Storage"
        PostgreSQL[(PostgreSQL<br/>Database)]
        CloudinaryStorage[Cloudinary<br/>Media Storage]
    end
    
    subgraph "External APIs"
        PesapalAPI[Pesapal API<br/>Payment Gateway]
        TwilioAPI[Twilio API<br/>Messaging]
    end
    
    Ecommerce -->|REST API<br/>/api/v1/public/| API
    AdminPanel -->|REST API<br/>/api/inventory/| API
    AdminPanel -->|Token Auth| API
    AdminUI -->|Direct Access| API
    
    API -->|ORM Queries| PostgreSQL
    API -->|Image Uploads| CloudinaryStorage
    API -->|Payment Initiation| PesapalAPI
    API -->|Payment Callbacks| PesapalAPI
    API -->|Send Messages| TwilioAPI
    
    style Ecommerce fill:#4caf50
    style AdminPanel fill:#4caf50
    style API fill:#9c27b0
    style AdminUI fill:#9c27b0
    style PostgreSQL fill:#f44336
    style CloudinaryStorage fill:#ff9800
    style PesapalAPI fill:#2196f3
    style TwilioAPI fill:#2196f3
```

### Container Responsibilities

#### E-commerce Frontend (Next.js)
- **Technology**: Next.js 14, React, TypeScript, Tailwind CSS
- **Responsibilities**:
  - Product browsing and search
  - Shopping cart management
  - Checkout flow
  - Order tracking
  - Promotions display
  - SEO optimization

#### Admin Frontend (React)
- **Technology**: Create React App, React, TypeScript
- **Responsibilities**:
  - Inventory management
  - Order processing
  - Admin user management
  - Reports and analytics
  - Content management

#### Django REST API
- **Technology**: Django 5.2.7, Django REST Framework, drf-spectacular
- **Responsibilities**:
  - Business logic
  - Data validation
  - Authentication & authorization
  - API endpoints
  - Payment processing
  - Notification services

#### PostgreSQL Database
- **Responsibilities**:
  - Product catalog
  - Inventory units
  - Orders and transactions
  - User management
  - Reviews and promotions

---

## Level 3: Component Diagram - Backend

Detailed view of backend components and their interactions.

```mermaid
graph TB
    subgraph "Django REST API"
        subgraph "API Layer"
            PublicAPI[Public API Views<br/>views_public.py]
            AdminAPI[Admin API Views<br/>views.py]
            AuthAPI[Auth Endpoints<br/>Token Login]
        end
        
        subgraph "Service Layer"
            CartService[Cart Service<br/>cart_service.py]
            CustomerService[Customer Service<br/>customer_service.py]
            PaymentService[Pesapal Payment Service<br/>pesapal_payment_service.py]
            LeadService[Lead Service<br/>lead_service.py]
            InterestService[Interest Service<br/>interest_service.py]
            ReceiptService[Receipt Service<br/>receipt_service.py]
            WhatsAppService[WhatsApp Service<br/>whatsapp_service.py]
        end
        
        subgraph "Model Layer"
            ProductModel[Product Models<br/>Product, Brand, Category]
            InventoryModel[Inventory Models<br/>InventoryUnit, Cart, CartItem]
            OrderModel[Order Models<br/>Order, OrderItem, Lead]
            UserModel[User Models<br/>User, Admin, Customer]
            PaymentModel[Payment Models<br/>PesapalPayment, PaymentNotification]
        end
        
        subgraph "Middleware & Utils"
            CORS[CORS Middleware]
            AuthMiddleware[Authentication Middleware]
            BrandMiddleware[Brand Middleware]
            CloudinaryUtils[Cloudinary Utils]
        end
    end
    
    subgraph "External Services"
        PesapalAPI[Pesapal API]
        TwilioAPI[Twilio API]
        CloudinaryAPI[Cloudinary API]
    end
    
    PublicAPI --> CartService
    PublicAPI --> CustomerService
    AdminAPI --> PaymentService
    AdminAPI --> LeadService
    AdminAPI --> InterestService
    
    CartService --> InventoryModel
    CustomerService --> UserModel
    PaymentService --> PaymentModel
    PaymentService --> PesapalAPI
    LeadService --> OrderModel
    InterestService --> InventoryModel
    ReceiptService --> OrderModel
    WhatsAppService --> TwilioAPI
    
    ProductModel --> CloudinaryUtils
    InventoryModel --> CloudinaryUtils
    CloudinaryUtils --> CloudinaryAPI
    
    AuthAPI --> UserModel
    
    style PublicAPI fill:#81c784
    style AdminAPI fill:#64b5f6
    style AuthAPI fill:#ffb74d
    style CartService fill:#ba68c8
    style CustomerService fill:#ba68c8
    style PaymentService fill:#ba68c8
    style LeadService fill:#ba68c8
    style ProductModel fill:#e57373
    style InventoryModel fill:#e57373
    style OrderModel fill:#e57373
    style UserModel fill:#e57373
```

### Backend Components

#### API Layer
- **Public API Views** (`views_public.py`): Customer-facing endpoints
  - Products listing
  - Cart operations
  - Promotions
  - Budget search
  
- **Admin API Views** (`views.py`): Admin-only endpoints
  - Inventory management
  - Order processing
  - User management
  - Reports

#### Service Layer
- **Cart Service**: Shopping cart operations
- **Customer Service**: Customer management and recognition
- **Payment Service**: Pesapal payment integration
- **Lead Service**: Lead creation and management
- **Interest Service**: Product interest tracking
- **Receipt Service**: Order receipt generation
- **WhatsApp Service**: Notification delivery

---

## Level 4: Component Diagram - Frontend

Frontend application structure and components.

```mermaid
graph TB
    subgraph "E-commerce Frontend - Next.js"
        subgraph "Pages"
            HomePage[Home Page<br/>Stories, Promotions]
            ProductsPage[Products Page<br/>Listing & Search]
            ProductDetail[Product Detail<br/>Single Product View]
            CartPage[Cart Page<br/>Cart Management]
            CheckoutPage[Checkout Page<br/>Order Creation]
            OrderPage[Order Page<br/>Order Tracking]
        end
        
        subgraph "Components"
            Header[Header Component]
            Footer[Footer Component]
            ProductCard[Product Card]
            ProductGrid[Product Grid]
            CartSummary[Cart Summary]
            StoriesCarousel[Stories Carousel]
        end
        
        subgraph "API Layer"
            PublicAPIClient[Public API Client<br/>lib/api/]
            ReactQueryHooks[React Query Hooks<br/>lib/hooks/]
        end
        
        subgraph "State Management"
            CartContext[Cart Context]
            BrandContext[Brand Context]
        end
    end
    
    subgraph "Admin Frontend - React"
        subgraph "Pages"
            InventoryPage[Inventory Management]
            OrdersPage[Order Management]
            ProductsPageAdmin[Product Management]
            AdminUsersPage[Admin User Management]
        end
        
        subgraph "Components"
            DataTable[Data Table]
            FormComponents[Form Components]
            Charts[Charts & Reports]
        end
        
        subgraph "API Layer"
            AdminAPIClient[Admin API Client]
            AuthService[Auth Service]
        end
    end
    
    subgraph "Backend API"
        DjangoAPI[Django REST API]
    end
    
    HomePage --> StoriesCarousel
    ProductsPage --> ProductGrid
    ProductGrid --> ProductCard
    CartPage --> CartSummary
    CheckoutPage --> PublicAPIClient
    
    PublicAPIClient --> ReactQueryHooks
    ReactQueryHooks --> DjangoAPI
    CartContext --> CartPage
    
    InventoryPage --> AdminAPIClient
    OrdersPage --> AdminAPIClient
    AdminAPIClient --> AuthService
    AuthService --> DjangoAPI
    
    style HomePage fill:#4caf50
    style ProductsPage fill:#4caf50
    style CartPage fill:#4caf50
    style InventoryPage fill:#2196f3
    style OrdersPage fill:#2196f3
    style DjangoAPI fill:#9c27b0
```

---

## Database Schema Diagram

High-level database relationships.

```mermaid
erDiagram
    User ||--o{ Admin : "has"
    User ||--o{ Customer : "has"
    Admin }o--o{ Brand : "manages"
    Admin }o--o{ AdminRole : "has"
    
    Brand ||--o{ Product : "belongs_to"
    Brand ||--o{ Promotion : "belongs_to"
    Brand ||--o{ Cart : "belongs_to"
    Brand ||--o{ Order : "belongs_to"
    
    Product ||--o{ ProductImage : "has"
    Product ||--o{ InventoryUnit : "has"
    Product ||--o{ Review : "has"
    Product ||--o{ ProductAccessory : "has_accessories"
    
    InventoryUnit ||--o{ InventoryUnitImage : "has"
    InventoryUnit ||--o{ CartItem : "in_cart"
    InventoryUnit ||--o{ OrderItem : "ordered"
    
    Cart ||--o{ CartItem : "contains"
    Cart }o--|| Customer : "belongs_to"
    
    Order ||--o{ OrderItem : "contains"
    Order }o--|| Customer : "placed_by"
    Order ||--o| PesapalPayment : "has_payment"
    Order ||--o| Lead : "converted_from"
    
    PesapalPayment ||--o{ PaymentNotification : "has_notifications"
    
    Customer ||--o{ Review : "writes"
    Customer ||--o{ Interest : "shows"
    
    Promotion ||--o{ PromotionImage : "has"
    
    User {
        int id PK
        string username
        string email
        string password
    }
    
    Brand {
        int id PK
        string code UK
        string name
        string domain
    }
    
    Product {
        int id PK
        int brand_id FK
        string name
        string slug
        text description
    }
    
    InventoryUnit {
        int id PK
        int product_id FK
        string status
        decimal price
        string sale_status
    }
    
    Order {
        uuid order_id PK
        int customer_id FK
        int brand_id FK
        decimal total_amount
        string status
    }
    
    Cart {
        int id PK
        int brand_id FK
        string session_key
        string customer_phone
    }
```

---

## Service Interaction Diagrams

### Cart Service Flow

```mermaid
sequenceDiagram
    participant Customer
    participant Frontend
    participant CartAPI
    participant CartService
    participant DB
    
    Customer->>Frontend: Add to Cart
    Frontend->>CartAPI: POST /api/v1/public/cart/
    CartAPI->>CartService: get_or_create_cart()
    CartService->>DB: Query Cart by session/phone
    DB-->>CartService: Cart or None
    alt Cart Not Found
        CartService->>DB: Create New Cart
    end
    CartService->>DB: Add CartItem
    DB-->>CartService: CartItem Created
    CartService-->>CartAPI: Cart with Items
    CartAPI-->>Frontend: Cart Response
    Frontend-->>Customer: Cart Updated
```

### Payment Flow

```mermaid
sequenceDiagram
    participant Customer
    participant Frontend
    participant OrderAPI
    participant PaymentService
    participant PesapalAPI
    participant IPNHandler
    
    Customer->>Frontend: Initiate Checkout
    Frontend->>OrderAPI: Create Order
    OrderAPI->>OrderAPI: Create Order & OrderItems
    OrderAPI-->>Frontend: Order Created
    
    Customer->>Frontend: Pay Now
    Frontend->>OrderAPI: POST /orders/{id}/initiate_payment/
    OrderAPI->>PaymentService: initiate_payment()
    PaymentService->>PesapalAPI: Submit Order Request
    PesapalAPI-->>PaymentService: Redirect URL
    PaymentService-->>OrderAPI: Payment Initiated
    OrderAPI-->>Frontend: Redirect URL
    Frontend->>Customer: Redirect to Pesapal
    
    Customer->>PesapalAPI: Complete Payment
    PesapalAPI->>IPNHandler: POST /pesapal/ipn/
    IPNHandler->>PaymentService: Process IPN
    PaymentService->>PaymentService: Update Order Status
    PaymentService->>PaymentService: Update Unit Status
    PesapalAPI->>Frontend: Callback URL
    Frontend->>Customer: Payment Success
```

### Order Processing Flow

```mermaid
sequenceDiagram
    participant Admin
    participant AdminFrontend
    participant OrderAPI
    participant OrderService
    participant PaymentService
    participant NotificationService
    participant DB
    
    Admin->>AdminFrontend: View Orders
    AdminFrontend->>OrderAPI: GET /api/inventory/orders/
    OrderAPI->>DB: Query Orders
    DB-->>OrderAPI: Orders List
    OrderAPI-->>AdminFrontend: Orders Data
    
    Admin->>AdminFrontend: Confirm Payment
    AdminFrontend->>OrderAPI: POST /orders/{id}/confirm_payment/
    OrderAPI->>OrderService: confirm_payment()
    OrderService->>DB: Update Order Status
    OrderService->>DB: Update Unit Sale Status
    OrderService->>PaymentService: Mark Payment Confirmed
    OrderService->>NotificationService: Send Confirmation
    NotificationService->>NotificationService: Send WhatsApp/SMS
    OrderService-->>OrderAPI: Payment Confirmed
    OrderAPI-->>AdminFrontend: Success Response
```

---

## API Flow Diagrams

### Public API Endpoints

```mermaid
graph LR
    subgraph "Public API - /api/v1/public/"
        Products[GET /products/<br/>List Products]
        ProductDetail[GET /products/:id<br/>Product Details]
        Cart[POST /cart/<br/>Add to Cart]
        CartGet[GET /cart/<br/>Get Cart]
        Promotions[GET /promotions/<br/>List Promotions]
        Reviews[GET /reviews/<br/>Product Reviews]
        BudgetSearch[POST /phone-search/<br/>Budget Search]
    end
    
    Products --> ProductDetail
    Products --> Cart
    Cart --> CartGet
    Products --> Reviews
    Products --> Promotions
    Products --> BudgetSearch
    
    style Products fill:#4caf50
    style Cart fill:#ff9800
    style Promotions fill:#2196f3
```

### Admin API Endpoints

```mermaid
graph TB
    subgraph "Admin API - /api/inventory/"
        Auth[POST /auth/token/login/<br/>Admin Login]
        
        subgraph "Inventory Management"
            ProductsAdmin[CRUD /products/<br/>Product Management]
            UnitsAdmin[CRUD /units/<br/>Unit Management]
            ImagesAdmin[CRUD /images/<br/>Image Management]
        end
        
        subgraph "Order Management"
            OrdersAdmin[CRUD /orders/<br/>Order Management]
            OrderReceipt[GET /orders/:id/receipt/<br/>Generate Receipt]
            ConfirmPayment[POST /orders/:id/confirm_payment/<br/>Confirm Payment]
            InitiatePayment[POST /orders/:id/initiate_payment/<br/>Initiate Payment]
        end
        
        subgraph "User Management"
            Admins[CRUD /admins/<br/>Admin Users]
            AdminRoles[CRUD /admin-roles/<br/>Roles Management]
        end
        
        subgraph "Content Management"
            PromotionsAdmin[CRUD /promotions/<br/>Promotions]
            ReviewsAdmin[CRUD /reviews/<br/>Reviews]
        end
        
        subgraph "Reports & Analytics"
            Reports[GET /reports/<br/>Generate Reports]
            StockAlerts[GET /stock-alerts/<br/>Stock Alerts]
        end
    end
    
    Auth --> ProductsAdmin
    Auth --> UnitsAdmin
    Auth --> OrdersAdmin
    Auth --> Admins
    Auth --> PromotionsAdmin
    Auth --> Reports
    
    OrdersAdmin --> OrderReceipt
    OrdersAdmin --> ConfirmPayment
    OrdersAdmin --> InitiatePayment
    
    style Auth fill:#ff9800
    style OrdersAdmin fill:#4caf50
    style ProductsAdmin fill:#2196f3
    style Reports fill:#9c27b0
```

---

## Technology Stack Summary

### Backend
- **Framework**: Django 5.2.7
- **API**: Django REST Framework 3.16.1
- **Database**: PostgreSQL (via psycopg3)
- **Authentication**: Token Authentication
- **API Documentation**: drf-spectacular (OpenAPI 3.0)
- **Image Storage**: Cloudinary
- **Payment**: Pesapal API
- **Notifications**: Twilio

### Frontend - E-commerce
- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **State Management**: React Query
- **API Client**: Generated from OpenAPI

### Frontend - Admin
- **Framework**: Create React App
- **Language**: TypeScript
- **State Management**: React Query
- **API Client**: Generated from OpenAPI

### Infrastructure
- **Backend Hosting**: Railway/Heroku
- **Frontend Hosting**: Vercel/Netlify
- **Database**: PostgreSQL (managed)
- **CDN**: Cloudinary

---

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        subgraph "Frontend Layer"
            EcommerceVercel[E-commerce Frontend<br/>Vercel]
            AdminVercel[Admin Frontend<br/>Vercel/Netlify]
        end
        
        subgraph "Backend Layer"
            DjangoRailway[Django Backend<br/>Railway/Heroku]
        end
        
        subgraph "Database Layer"
            PostgresDB[(PostgreSQL<br/>Managed Database)]
        end
        
        subgraph "External Services"
            CloudinaryCDN[Cloudinary CDN]
            PesapalProd[Pesapal Production]
            TwilioProd[Twilio Production]
        end
    end
    
    EcommerceVercel -->|HTTPS| DjangoRailway
    AdminVercel -->|HTTPS| DjangoRailway
    DjangoRailway -->|Connection Pool| PostgresDB
    DjangoRailway -->|API Calls| CloudinaryCDN
    DjangoRailway -->|API Calls| PesapalProd
    DjangoRailway -->|API Calls| TwilioProd
    
    style EcommerceVercel fill:#4caf50
    style AdminVercel fill:#4caf50
    style DjangoRailway fill:#9c27b0
    style PostgresDB fill:#f44336
```

---

## How to View These Diagrams

### Option 1: Mermaid Live Editor
1. Copy any Mermaid diagram code
2. Go to https://mermaid.live
3. Paste the code
4. Export as PNG/SVG

### Option 2: VS Code Extension
1. Install "Markdown Preview Mermaid Support" extension
2. Open this file in VS Code
3. Use Markdown preview to see rendered diagrams

### Option 3: GitHub/GitLab
- These diagrams will render automatically in markdown files on GitHub/GitLab

### Option 4: Generate Static Images
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Generate PNG from this file
mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture_diagrams.png
```

---

## Next Steps

1. **Generate Database ER Diagram**: Run `python manage.py graph_models` to create detailed database diagrams
2. **API Documentation**: View interactive API docs at `/api/schema/swagger-ui/`
3. **Sequence Diagrams**: Create detailed sequence diagrams for complex flows
4. **Deployment Diagrams**: Document specific deployment configurations

---

*Last Updated: $(date)*
*Generated for Affordable Gadgets Platform*
