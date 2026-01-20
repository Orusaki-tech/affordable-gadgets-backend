#!/bin/bash

# Convert all extracted Mermaid diagrams to PNG files
# Requires: npm install -g @mermaid-js/mermaid-cli

echo "=========================================="
echo "  Convert Mermaid Diagrams to PNG"
echo "=========================================="
echo ""

# Check if Mermaid CLI is installed
if ! command -v mmdc &> /dev/null; then
    echo "⚠️  Mermaid CLI not found!"
    echo ""
    echo "Install it with:"
    echo "  npm install -g @mermaid-js/mermaid-cli"
    echo ""
    echo "Or use the online method:"
    echo "  1. Go to https://mermaid.live"
    echo "  2. Open any .mmd file from exported_diagrams/mermaid_files/"
    echo "  3. Copy content and paste into editor"
    echo "  4. Click 'Download PNG' or 'Download SVG'"
    exit 1
fi

# Create output directory
mkdir -p exported_diagrams/individual

echo "🔄 Converting diagrams to PNG..."
echo ""

count=0
for mermaid_file in exported_diagrams/mermaid_files/*.mmd; do
    if [ -f "$mermaid_file" ]; then
        filename=$(basename "$mermaid_file" .mmd)
        png_file="exported_diagrams/individual/${filename}.png"
        
        mmdc -i "$mermaid_file" -o "$png_file" -b white -w 1920 -H 1080 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "  ✅ $(basename $png_file)"
            count=$((count + 1))
        else
            echo "  ⚠️  Failed: $(basename $mermaid_file)"
        fi
    fi
done

echo ""
echo "=========================================="
echo "✅ Conversion complete! Generated $count PNG files"
echo ""
echo "📁 PNG files saved to: exported_diagrams/individual/"
echo ""
ls -lh exported_diagrams/individual/*.png 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
echo "=========================================="
