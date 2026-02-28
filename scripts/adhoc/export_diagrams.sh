#!/bin/bash

# Quick script to export diagrams as images

echo "=========================================="
echo "  Export Architecture Diagrams"
echo "=========================================="
echo ""

# Check for Mermaid CLI
if ! command -v mmdc &> /dev/null; then
    echo "⚠️  Mermaid CLI not found!"
    echo ""
    echo "Install with: npm install -g @mermaid-js/mermaid-cli"
    echo ""
    echo "Or use the online method:"
    echo "  1. Go to https://mermaid.live"
    echo "  2. Copy diagram code from .md files"
    echo "  3. Paste and download"
    exit 1
fi

# Create output directory
mkdir -p exported_diagrams
cd exported_diagrams

echo "📊 Exporting diagrams..."
echo ""

# Export backend diagrams
cd ../affordable-gadgets-backend
mmdc -i ARCHITECTURE_DIAGRAMS.md -o ../exported_diagrams/architecture_diagrams.png 2>/dev/null && echo "✅ architecture_diagrams.png"
mmdc -i SERVICES_DETAILED.md -o ../exported_diagrams/services_detailed.png 2>/dev/null && echo "✅ services_detailed.png"
mmdc -i API_ENDPOINTS_REFERENCE.md -o ../exported_diagrams/api_endpoints.png 2>/dev/null && echo "✅ api_endpoints.png"

# Export frontend diagrams
cd ../affordable-gadgets-frontend
mmdc -i FRONTEND_ARCHITECTURE.md -o ../exported_diagrams/frontend_architecture.png 2>/dev/null && echo "✅ frontend_architecture.png"

cd ../exported_diagrams

echo ""
echo "=========================================="
echo "✅ Export complete!"
echo ""
echo "📁 Files saved to: $(pwd)"
echo ""
ls -lh *.png 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
echo ""
echo "💡 Tip: Use https://mermaid.live for individual diagrams"
echo "=========================================="
