# How to Download Diagrams as Images

Guide to export and download all architecture diagrams as PNG/SVG/PDF files.

---

## 🚀 Quick Method (No Installation Required)

### Method 1: Mermaid Live Editor (Easiest)

1. **Go to**: https://mermaid.live
2. **Open any diagram file**:
   - `ARCHITECTURE_DIAGRAMS.md`
   - `SERVICES_DETAILED.md`
   - `FRONTEND_ARCHITECTURE.md`
3. **Copy the Mermaid code** from any diagram block (between ```mermaid and ```)
4. **Paste into Mermaid Live Editor**
5. **Click "Download PNG" or "Download SVG"**
6. **Repeat for each diagram**

**Example**: Copy this code from `ARCHITECTURE_DIAGRAMS.md`:
```mermaid
graph TB
    Customer[Customer]
    Admin[Admin User]
    Ecommerce[E-commerce Frontend<br/>Next.js]
```

---

## 🛠️ Automated Method (Requires Installation)

### Step 1: Install Mermaid CLI

```bash
npm install -g @mermaid-js/mermaid-cli
```

### Step 2: Generate All Diagrams

```bash
cd affordable-gadgets-backend

# Generate all diagrams from markdown files
mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture_diagrams.png
mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture_diagrams.pdf
mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture_diagrams.svg

mmdc -i SERVICES_DETAILED.md -o services_detailed.png
mmdc -i API_ENDPOINTS_REFERENCE.md -o api_endpoints.png

cd ../affordable-gadgets-frontend
mmdc -i FRONTEND_ARCHITECTURE.md -o frontend_architecture.png
```

**Output**: PNG/SVG/PDF files will be created in the same directory.

---

## 📊 Database Diagrams (Requires Graphviz)

### Step 1: Install Graphviz

**macOS:**
```bash
brew install graphviz
```

**Linux:**
```bash
sudo apt-get install graphviz
```

**Windows:**
Download from: https://graphviz.org/download/

### Step 2: Generate Database Diagrams

```bash
cd affordable-gadgets-backend

# Run the generation script
./generate_diagrams.sh
```

**Output**: 
- `database_schema.png` - High-level ER diagram
- `database_detailed.png` - Detailed model relationships

---

## 🎯 Individual Diagram Export

### Export Specific Diagrams

You can extract individual diagrams from the markdown files:

1. **Open the markdown file** (e.g., `ARCHITECTURE_DIAGRAMS.md`)
2. **Find the diagram** you want (search for ```mermaid)
3. **Copy the code block** (everything between ```mermaid and ```)
4. **Paste at https://mermaid.live**
5. **Download as PNG/SVG**

### Example: Export System Context Diagram

1. Open `ARCHITECTURE_DIAGRAMS.md`
2. Find "Level 1: System Context Diagram"
3. Copy the mermaid code block
4. Paste at mermaid.live
5. Download PNG

---

## 📁 Complete Export Script

Create a script to export all diagrams at once:

```bash
#!/bin/bash
# export_all_diagrams.sh

# Install if not already installed
if ! command -v mmdc &> /dev/null; then
    echo "Installing Mermaid CLI..."
    npm install -g @mermaid-js/mermaid-cli
fi

cd affordable-gadgets-backend

echo "Exporting backend diagrams..."
mmdc -i ARCHITECTURE_DIAGRAMS.md -o diagrams/architecture_diagrams.png
mmdc -i SERVICES_DETAILED.md -o diagrams/services_detailed.png
mmdc -i API_ENDPOINTS_REFERENCE.md -o diagrams/api_endpoints.png

cd ../affordable-gadgets-frontend

echo "Exporting frontend diagrams..."
mmdc -i FRONTEND_ARCHITECTURE.md -o diagrams/frontend_architecture.png

echo "✅ All diagrams exported to diagrams/ folder"
```

---

## 🌐 Online Export (GitHub)

### Method 1: GitHub + Browser Extension

1. **View diagram on GitHub** (diagrams render automatically)
2. **Right-click on diagram** → "Save image as..."
3. **Save as PNG**

### Method 2: GitHub Raw + Mermaid Live

1. **Get raw markdown URL** from GitHub:
   ```
   https://raw.githubusercontent.com/Orusaki-tech/affordable-gadgets-backend/main/ARCHITECTURE_DIAGRAMS.md
   ```
2. **Copy diagram code** from raw view
3. **Paste at https://mermaid.live**
4. **Download**

---

## 📋 Diagram List

Here are all the diagrams you can export:

### From ARCHITECTURE_DIAGRAMS.md:
1. System Context Diagram
2. Container Diagram
3. Backend Component Diagram
4. Frontend Component Diagram
5. Database Schema Diagram
6. Cart Service Flow
7. Payment Flow
8. Order Processing Flow
9. API Endpoint Diagrams

### From SERVICES_DETAILED.md:
1. Cart Service Flow
2. Customer Service Flow
3. Payment Service Flow
4. Lead Service Flow
5. Service Dependency Graph

### From FRONTEND_ARCHITECTURE.md:
1. Component Hierarchy
2. API Integration Flow
3. Routing Structure
4. Product Browsing Flow
5. Add to Cart Flow
6. Checkout Flow

---

## 💡 Tips

### High Quality Exports
- Use **SVG** for scalable vector graphics (best for presentations)
- Use **PNG** for raster images (best for documents)
- Use **PDF** for multi-page documents

### Batch Export
```bash
# Export all as PNG
for file in *.md; do
    mmdc -i "$file" -o "${file%.md}.png"
done
```

### Custom Styling
Mermaid Live Editor allows you to:
- Change colors
- Adjust layout
- Add custom CSS
- Export with custom themes

---

## 🔧 Troubleshooting

### "mmdc: command not found"
```bash
npm install -g @mermaid-js/mermaid-cli
```

### "dot: command not found"
```bash
# macOS
brew install graphviz

# Linux
sudo apt-get install graphviz
```

### Diagrams not rendering
- Check Mermaid syntax is correct
- Use https://mermaid.live to validate
- Ensure code blocks are properly formatted

---

## 📦 Quick Export Commands

```bash
# One-liner to export main architecture diagram
cd affordable-gadgets-backend && mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture.png

# Export all markdown files as images
find . -name "*.md" -exec mmdc -i {} -o {}.png \;

# Export with custom background
mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture.png -b white
```

---

*Last Updated: $(date)*
