#!/bin/bash

# Script to export ALL diagrams from all markdown files
# This script will extract Mermaid diagrams and prepare them for export

echo "=========================================="
echo "  Export All Architecture Diagrams"
echo "=========================================="
echo ""

# Create directories
mkdir -p exported_diagrams/individual
mkdir -p exported_diagrams/mermaid_files

BACKEND_DIR="$(pwd)"
FRONTEND_DIR="../affordable-gadgets-frontend"

echo "📊 Extracting diagrams from markdown files..."
echo ""

# Function to extract mermaid diagrams from a file using Python
extract_mermaid() {
    local file="$1"
    local output_dir="$2"
    local basename=$(basename "$file" .md)
    
    if [ ! -f "$file" ]; then
        echo "⚠️  File not found: $file"
        return
    fi
    
    echo "Processing: $file"
    
    python3 << EOF
import re
import os

with open("$file", "r") as f:
    content = f.read()

# Find all mermaid code blocks
pattern = r'```mermaid\n(.*?)\n```'
matches = re.findall(pattern, content, re.DOTALL)

if matches:
    for i, diagram in enumerate(matches, 1):
        output_file = os.path.join("$output_dir", "${basename}_diagram_{}.mmd".format(i))
        with open(output_file, "w") as out:
            out.write(diagram.strip())
        print(f"  ✅ Extracted diagram {i}")
else:
    print("  ⚠️  No diagrams found")
EOF
}

# Extract from backend files
extract_mermaid "$BACKEND_DIR/ARCHITECTURE_DIAGRAMS.md" "$BACKEND_DIR/exported_diagrams/mermaid_files"
extract_mermaid "$BACKEND_DIR/SERVICES_DETAILED.md" "$BACKEND_DIR/exported_diagrams/mermaid_files"
extract_mermaid "$BACKEND_DIR/API_ENDPOINTS_REFERENCE.md" "$BACKEND_DIR/exported_diagrams/mermaid_files"
extract_mermaid "$BACKEND_DIR/ARCHITECTURE_INDEX.md" "$BACKEND_DIR/exported_diagrams/mermaid_files"
extract_mermaid "$BACKEND_DIR/DIAGRAMS_QUICK_START.md" "$BACKEND_DIR/exported_diagrams/mermaid_files"

# Extract from frontend files
if [ -f "$FRONTEND_DIR/FRONTEND_ARCHITECTURE.md" ]; then
    extract_mermaid "$FRONTEND_DIR/FRONTEND_ARCHITECTURE.md" "$BACKEND_DIR/exported_diagrams/mermaid_files"
fi

echo ""
echo "=========================================="
echo "✅ Diagram extraction complete!"
echo ""

# Check if Mermaid CLI is installed
if command -v mmdc &> /dev/null; then
    echo "🔄 Mermaid CLI found. Generating PNG files..."
    echo ""
    
    # Generate PNGs from extracted mermaid files
    for mermaid_file in exported_diagrams/mermaid_files/*.mmd; do
        if [ -f "$mermaid_file" ]; then
            filename=$(basename "$mermaid_file" .mmd)
            png_file="exported_diagrams/individual/${filename}.png"
            mmdc -i "$mermaid_file" -o "$png_file" -b white 2>/dev/null
            if [ $? -eq 0 ]; then
                echo "  ✅ $(basename $png_file)"
            fi
        fi
    done
    
    echo ""
    echo "📁 PNG files saved to: exported_diagrams/individual/"
else
    echo "⚠️  Mermaid CLI not installed."
    echo ""
    echo "To generate PNG files, install Mermaid CLI:"
    echo "  npm install -g @mermaid-js/mermaid-cli"
    echo ""
    echo "Or use the online method:"
    echo "  1. Go to https://mermaid.live"
    echo "  2. Open any .mmd file from exported_diagrams/mermaid_files/"
    echo "  3. Copy content and paste into editor"
    echo "  4. Click 'Download PNG' or 'Download SVG'"
    echo ""
    echo "📁 Mermaid source files saved to: exported_diagrams/mermaid_files/"
fi

echo ""
echo "=========================================="
echo "📋 Summary:"
echo ""
echo "Mermaid source files: exported_diagrams/mermaid_files/"
if [ -d "exported_diagrams/individual" ] && [ -n "$(ls -A exported_diagrams/individual/*.png 2>/dev/null)" ]; then
    echo "PNG image files: exported_diagrams/individual/"
    echo ""
    echo "Generated PNG files:"
    ls -lh exported_diagrams/individual/*.png 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
fi
echo ""
echo "💡 To export manually:"
echo "   1. Go to https://mermaid.live"
echo "   2. Open any .mmd file from exported_diagrams/mermaid_files/"
echo "   3. Copy content and paste into editor"
echo "   4. Click 'Download PNG' or 'Download SVG'"
echo "=========================================="
