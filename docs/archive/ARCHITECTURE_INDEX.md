# Architecture Documentation Index

Complete guide to all architecture and service diagrams for the Affordable Gadgets Platform.

---

## 📚 Documentation Files

### 1. [ARCHITECTURE_DIAGRAMS.md](./ARCHITECTURE_DIAGRAMS.md)
**Comprehensive architecture diagrams at multiple levels**

- ✅ Level 1: System Context Diagram
- ✅ Level 2: Container Diagram  
- ✅ Level 3: Component Diagram - Backend
- ✅ Level 4: Component Diagram - Frontend
- ✅ Database Schema Diagram
- ✅ Service Interaction Diagrams
- ✅ API Flow Diagrams
- ✅ Deployment Architecture

**View**: Open in VS Code with Mermaid extension or visit https://mermaid.live

---

### 2. [SERVICES_DETAILED.md](./SERVICES_DETAILED.md)
**Detailed documentation of all backend services**

- ✅ Cart Service
- ✅ Customer Service
- ✅ Payment Service (Pesapal)
- ✅ Lead Service
- ✅ Interest Service
- ✅ Receipt Service
- ✅ WhatsApp Service
- ✅ Service Dependencies

**Includes**: Flow diagrams, method documentation, error handling

---

### 3. [API_ENDPOINTS_REFERENCE.md](./API_ENDPOINTS_REFERENCE.md)
**Complete API reference documentation**

- ✅ Public API Endpoints
- ✅ Admin API Endpoints
- ✅ Authentication Endpoints
- ✅ Request/Response Formats
- ✅ Error Handling
- ✅ Rate Limiting

**Use Cases**: API integration, testing, documentation

---

### 4. [../affordable-gadgets-frontend/FRONTEND_ARCHITECTURE.md](../affordable-gadgets-frontend/FRONTEND_ARCHITECTURE.md)
**Frontend architecture documentation**

- ✅ Application Structure
- ✅ Component Hierarchy
- ✅ State Management
- ✅ API Integration
- ✅ Routing
- ✅ Data Flow Diagrams

---

## 🎨 Viewing Diagrams

### Option 1: VS Code (Recommended)
1. Install "Markdown Preview Mermaid Support" extension
2. Open any `.md` file
3. Press `Cmd+Shift+V` (Mac) or `Ctrl+Shift+V` (Windows) to preview
4. Diagrams will render automatically

### Option 2: Mermaid Live Editor
1. Copy Mermaid diagram code from any `.md` file
2. Go to https://mermaid.live
3. Paste the code
4. Export as PNG/SVG/PDF

### Option 3: GitHub/GitLab
- Diagrams render automatically in markdown files
- Just push to repository and view online

### Option 4: Generate Static Images
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Generate images from markdown
mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture_diagrams.png
```

---

## 🗄️ Database Diagrams

### Generate ER Diagrams

```bash
# Make script executable
chmod +x generate_diagrams.sh

# Run diagram generation
./generate_diagrams.sh
```

**Requirements**:
- Python with Django
- Graphviz (`brew install graphviz` on macOS)
- Optional: Mermaid CLI for static images

**Output**:
- `database_schema.png` - High-level ER diagram
- `database_detailed.png` - Detailed model relationships

---

## 📊 Diagram Types Available

### 1. System Context Diagrams
**Purpose**: High-level view of system and external dependencies
**Location**: `ARCHITECTURE_DIAGRAMS.md` - Level 1

**Shows**:
- System boundaries
- External actors (Customers, Admins)
- External services (Cloudinary, Pesapal, Twilio)

---

### 2. Container Diagrams
**Purpose**: Technical building blocks and their responsibilities
**Location**: `ARCHITECTURE_DIAGRAMS.md` - Level 2

**Shows**:
- Frontend applications (Next.js, React)
- Backend services (Django API)
- Databases (PostgreSQL)
- External APIs

---

### 3. Component Diagrams
**Purpose**: Internal structure of applications
**Location**: `ARCHITECTURE_DIAGRAMS.md` - Level 3 & 4

**Shows**:
- Backend components (API layer, Services, Models)
- Frontend components (Pages, Components, State)
- Component interactions

---

### 4. Database Schema Diagrams
**Purpose**: Data model relationships
**Location**: `ARCHITECTURE_DIAGRAMS.md` - Database Schema section

**Shows**:
- Entity relationships
- Foreign keys
- Model associations

**Generate**: Run `./generate_diagrams.sh`

---

### 5. Sequence Diagrams
**Purpose**: Step-by-step interaction flows
**Location**: `ARCHITECTURE_DIAGRAMS.md` & `SERVICES_DETAILED.md`

**Shows**:
- Cart operations flow
- Payment processing flow
- Order confirmation flow
- Service interactions

---

### 6. State Diagrams
**Purpose**: State transitions
**Location**: `SERVICES_DETAILED.md`

**Shows**:
- Payment status flow
- Lead status flow
- Order status flow

---

### 7. API Flow Diagrams
**Purpose**: API endpoint relationships
**Location**: `ARCHITECTURE_DIAGRAMS.md` - API Flow Diagrams

**Shows**:
- Public API endpoints
- Admin API endpoints
- Endpoint relationships

---

## 🔍 Quick Reference

### Find Information About...

**System Architecture** → `ARCHITECTURE_DIAGRAMS.md`
- System context
- Container structure
- Component details

**Backend Services** → `SERVICES_DETAILED.md`
- Service methods
- Service flows
- Error handling

**API Endpoints** → `API_ENDPOINTS_REFERENCE.md`
- Endpoint URLs
- Request/response formats
- Authentication

**Frontend Structure** → `../affordable-gadgets-frontend/FRONTEND_ARCHITECTURE.md`
- Component hierarchy
- State management
- Routing

**Database Schema** → Run `./generate_diagrams.sh`
- Entity relationships
- Model structure

---

## 🛠️ Tools Used

### Diagram Generation
- **Mermaid**: Text-based diagramming (included in markdown)
- **Django Extensions**: Database ER diagrams (`graph_models`)
- **Graphviz**: Rendering engine for database diagrams

### Documentation
- **Markdown**: All documentation files
- **Mermaid**: All diagrams
- **OpenAPI**: API specification (`openapi.yaml`)

---

## 📝 Adding New Diagrams

### Adding Mermaid Diagrams

1. Edit the appropriate `.md` file
2. Add Mermaid code block:
   ```markdown
   ```mermaid
   graph TB
       A --> B
   ```
   ```
3. Diagrams render automatically in VS Code/GitHub

### Adding Database Diagrams

1. Update Django models
2. Run `./generate_diagrams.sh`
3. Diagrams auto-generate from models

---

## 🎯 Use Cases

### For Developers
- Understanding system architecture
- Onboarding new team members
- Planning new features
- Debugging issues

### For Stakeholders
- System overview
- Technology stack
- Integration points
- Deployment architecture

### For DevOps
- Deployment architecture
- Service dependencies
- Infrastructure requirements
- Monitoring points

---

## 🔄 Keeping Diagrams Updated

### When to Update

1. **New Service Added** → Update `ARCHITECTURE_DIAGRAMS.md` and `SERVICES_DETAILED.md`
2. **New API Endpoint** → Update `API_ENDPOINTS_REFERENCE.md`
3. **New Model** → Run `./generate_diagrams.sh` to regenerate database diagrams
4. **New Frontend Component** → Update `FRONTEND_ARCHITECTURE.md`
5. **Deployment Changes** → Update deployment diagrams in `ARCHITECTURE_DIAGRAMS.md`

### Update Checklist

- [ ] Update relevant diagram files
- [ ] Regenerate database diagrams if models changed
- [ ] Update API documentation if endpoints changed
- [ ] Test diagram rendering in VS Code
- [ ] Commit changes to repository

---

## 📞 Support

### Issues with Diagrams

1. **Diagrams not rendering**: Install Mermaid extension in VS Code
2. **Database diagrams not generating**: Install Graphviz
3. **Mermaid syntax errors**: Validate at https://mermaid.live

### Questions

- Check relevant documentation file first
- Review diagram comments for context
- Check OpenAPI spec for API details

---

## 📚 Additional Resources

- **Django Documentation**: https://docs.djangoproject.com/
- **Next.js Documentation**: https://nextjs.org/docs
- **Mermaid Documentation**: https://mermaid.js.org/
- **OpenAPI Specification**: `/openapi.yaml`
- **API Documentation**: `/api/schema/swagger-ui/`

---

*Last Updated: $(date)*
*Platform: Affordable Gadgets*
*Version: 1.0.0*
