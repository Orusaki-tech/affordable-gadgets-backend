#!/bin/bash

# Quick script to help view diagrams

echo "=========================================="
echo "  Affordable Gadgets - Diagram Viewer"
echo "=========================================="
echo ""

# Check if VS Code is installed
if command -v code &> /dev/null; then
    echo "✅ VS Code detected!"
    echo ""
    echo "To view diagrams:"
    echo "  1. Run: code ARCHITECTURE_INDEX.md"
    echo "  2. Press Cmd+Shift+V (Mac) or Ctrl+Shift+V (Windows)"
    echo "  3. Install 'Markdown Preview Mermaid Support' if prompted"
    echo ""
    read -p "Open ARCHITECTURE_INDEX.md in VS Code now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        code ARCHITECTURE_INDEX.md
    fi
else
    echo "VS Code not found. Install VS Code for best diagram viewing experience."
    echo ""
fi

echo ""
echo "📚 Available Documentation Files:"
echo ""
echo "  📊 ARCHITECTURE_INDEX.md          - Start here! Master index"
echo "  🎨 ARCHITECTURE_DIAGRAMS.md       - All architecture diagrams"
echo "  🔧 SERVICES_DETAILED.md          - Backend services documentation"
echo "  📡 API_ENDPOINTS_REFERENCE.md     - Complete API reference"
echo "  🚀 DIAGRAMS_QUICK_START.md        - Quick start guide"
echo ""

echo "🌐 View Online:"
echo "  GitHub: https://github.com/Orusaki-tech/affordable-gadgets-backend"
echo "  Mermaid Live: https://mermaid.live"
echo ""

echo "📁 File Locations:"
echo "  Backend docs: $(pwd)"
echo "  Frontend docs: ../affordable-gadgets-frontend/FRONTEND_ARCHITECTURE.md"
echo ""
