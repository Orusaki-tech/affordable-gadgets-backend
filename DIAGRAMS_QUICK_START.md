# Diagrams Quick Start Guide

Quick guide to viewing and using the architecture diagrams for Affordable Gadgets Platform.

---

## 🚀 Quick Start (5 minutes)

### Step 1: View Diagrams in VS Code

1. **Install Extension** (if not already installed):
   - Open VS Code
   - Go to Extensions (Cmd+Shift+X / Ctrl+Shift+X)
   - Search for "Markdown Preview Mermaid Support"
   - Install it

2. **Open Documentation**:
   - Open `ARCHITECTURE_INDEX.md` in VS Code
   - Press `Cmd+Shift+V` (Mac) or `Ctrl+Shift+V` (Windows)
   - All diagrams will render automatically!

### Step 2: Explore Different Levels

Start with the high-level view and drill down:

1. **System Context** → `ARCHITECTURE_DIAGRAMS.md` (Level 1)
   - See the big picture: customers, admins, external services

2. **Container View** → `ARCHITECTURE_DIAGRAMS.md` (Level 2)
   - Understand technical building blocks: frontends, backend, database

3. **Component Details** → `ARCHITECTURE_DIAGRAMS.md` (Level 3 & 4)
   - Deep dive into internal structure

4. **Service Details** → `SERVICES_DETAILED.md`
   - Understand how services work and interact

5. **API Reference** → `API_ENDPOINTS_REFERENCE.md`
   - Complete API documentation

---

## 📊 What Diagrams Are Available?

### ✅ Created and Ready to View

1. **System Context Diagram** - High-level system overview
2. **Container Diagram** - Technical architecture
3. **Backend Component Diagram** - Django services structure
4. **Frontend Component Diagram** - Next.js/React structure
5. **Database Schema Diagram** - ER diagram (Mermaid)
6. **Cart Service Flow** - Sequence diagram
7. **Payment Flow** - Complete payment process
8. **Order Processing Flow** - Order management
9. **API Endpoint Diagrams** - Public and Admin APIs
10. **Service Dependency Graph** - Service relationships

### 🔄 Can Be Generated

1. **Database ER Diagram (PNG)** - Run `./generate_diagrams.sh`
   - Requires: Graphviz installed
   - Output: `database_schema.png`

2. **Static Diagram Images** - Run `mmdc` command
   - Requires: Mermaid CLI installed
   - Output: PNG/PDF versions of all diagrams

---

## 🎯 Common Use Cases

### "I want to understand the overall system"
→ Open `ARCHITECTURE_DIAGRAMS.md` → Level 1: System Context Diagram

### "I need to know how payment works"
→ Open `ARCHITECTURE_DIAGRAMS.md` → Payment Flow section
→ Also see: `SERVICES_DETAILED.md` → Payment Service

### "I want to see all API endpoints"
→ Open `API_ENDPOINTS_REFERENCE.md`

### "I need to understand the database structure"
→ Open `ARCHITECTURE_DIAGRAMS.md` → Database Schema Diagram
→ Or run `./generate_diagrams.sh` for PNG version

### "I want to see how services interact"
→ Open `SERVICES_DETAILED.md` → Service Dependencies section

### "I need frontend architecture details"
→ Open `../affordable-gadgets-frontend/FRONTEND_ARCHITECTURE.md`

---

## 🛠️ Installation Requirements

### For Viewing (Required)
- ✅ VS Code with "Markdown Preview Mermaid Support" extension
- OR GitHub/GitLab account (diagrams render automatically)

### For Generating Static Images (Optional)

**Database Diagrams:**
```bash
# macOS
brew install graphviz

# Linux
sudo apt-get install graphviz

# Then run
./generate_diagrams.sh
```

**Mermaid Static Images:**
```bash
npm install -g @mermaid-js/mermaid-cli

# Generate from markdown
mmdc -i ARCHITECTURE_DIAGRAMS.md -o diagrams.png
```

---

## 📁 File Structure

```
affordable-gadgets-backend/
├── ARCHITECTURE_INDEX.md          # 📚 Start here - Index of all docs
├── ARCHITECTURE_DIAGRAMS.md       # 🎨 All architecture diagrams
├── SERVICES_DETAILED.md           # 🔧 Detailed service documentation
├── API_ENDPOINTS_REFERENCE.md     # 📡 Complete API reference
├── DIAGRAMS_QUICK_START.md        # 🚀 This file
├── generate_diagrams.sh           # 🔄 Script to generate PNG diagrams
└── openapi.yaml                   # 📋 OpenAPI specification

affordable-gadgets-frontend/
└── FRONTEND_ARCHITECTURE.md       # 🎨 Frontend architecture docs
```

---

## 💡 Tips

### Tip 1: Use VS Code Preview
- Open any `.md` file
- Press `Cmd+Shift+V` / `Ctrl+Shift+V`
- Diagrams render automatically
- Best viewing experience

### Tip 2: Export Diagrams
- Copy Mermaid code from any diagram
- Paste at https://mermaid.live
- Export as PNG/SVG/PDF
- Use in presentations

### Tip 3: Keep Updated
- Diagrams update automatically when you edit `.md` files
- Database diagrams regenerate when models change
- Run `./generate_diagrams.sh` after model changes

### Tip 4: Share with Team
- Push to GitHub/GitLab
- Diagrams render automatically online
- No special tools needed for viewers

---

## 🔍 Finding Specific Information

### Search by Topic

| Topic | File | Section |
|-------|------|---------|
| System Overview | ARCHITECTURE_DIAGRAMS.md | Level 1 |
| Backend Services | SERVICES_DETAILED.md | All sections |
| API Endpoints | API_ENDPOINTS_REFERENCE.md | All sections |
| Payment Flow | ARCHITECTURE_DIAGRAMS.md | Payment Flow |
| Cart Operations | SERVICES_DETAILED.md | Cart Service |
| Database Models | ARCHITECTURE_DIAGRAMS.md | Database Schema |
| Frontend Structure | FRONTEND_ARCHITECTURE.md | All sections |
| Deployment | ARCHITECTURE_DIAGRAMS.md | Deployment Architecture |

---

## ❓ Troubleshooting

### Diagrams not showing in VS Code?
1. Install "Markdown Preview Mermaid Support" extension
2. Reload VS Code
3. Open markdown preview again

### Database diagrams not generating?
1. Install Graphviz: `brew install graphviz` (macOS)
2. Check Python/Django is working: `python manage.py --version`
3. Run: `./generate_diagrams.sh`

### Mermaid syntax errors?
1. Copy diagram code
2. Paste at https://mermaid.live
3. Check error messages
4. Fix syntax and update file

---

## 🎓 Learning Path

### For New Team Members

1. **Day 1**: Read `ARCHITECTURE_INDEX.md` → Get overview
2. **Day 2**: Study `ARCHITECTURE_DIAGRAMS.md` → Understand structure
3. **Day 3**: Review `SERVICES_DETAILED.md` → Learn services
4. **Day 4**: Explore `API_ENDPOINTS_REFERENCE.md` → Understand APIs
5. **Day 5**: Review `FRONTEND_ARCHITECTURE.md` → Frontend structure

### For Developers

- **Backend Dev**: Focus on `SERVICES_DETAILED.md` and `API_ENDPOINTS_REFERENCE.md`
- **Frontend Dev**: Focus on `FRONTEND_ARCHITECTURE.md`
- **Full Stack**: Review all documentation files

---

## 📞 Need Help?

1. Check `ARCHITECTURE_INDEX.md` for complete index
2. Review relevant documentation file
3. Check OpenAPI spec: `/openapi.yaml`
4. View API docs: `/api/schema/swagger-ui/`

---

## ✨ Next Steps

1. ✅ View diagrams in VS Code
2. ✅ Explore different documentation levels
3. ✅ Generate static images (optional)
4. ✅ Share with team
5. ✅ Keep documentation updated

---

*Happy diagramming! 🎨*
