#!/bin/bash

# Script to generate architecture diagrams for Affordable Gadgets Platform

echo "Generating Architecture Diagrams..."

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "Error: manage.py not found. Please run this script from the Django project root."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Check if graphviz is installed
if ! command -v dot &> /dev/null; then
    echo "Warning: graphviz not found. Installing graphviz is required for database diagrams."
    echo "Install with: brew install graphviz (macOS) or apt-get install graphviz (Linux)"
fi

# Generate database ER diagram
echo "Generating database ER diagram..."
python manage.py graph_models inventory \
    -o database_schema.png \
    --settings=store.settings \
    --pygraphviz \
    --verbose-name \
    --group-models 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Database schema diagram generated: database_schema.png"
else
    echo "⚠ Database schema generation failed. Trying without pygraphviz..."
    python manage.py graph_models inventory \
        -o database_schema.png \
        --settings=store.settings \
        --verbose-name 2>&1
fi

# Generate detailed model diagram
echo "Generating detailed model diagram..."
python manage.py graph_models inventory \
    -o database_detailed.png \
    --settings=store.settings \
    --pygraphviz \
    --verbose-name \
    --exclude-models=ContentType,Permission,Group,Session,LogEntry 2>&1

# Generate Mermaid diagrams from markdown (if mmdc is installed)
if command -v mmdc &> /dev/null; then
    echo "Generating Mermaid diagrams..."
    mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture_diagrams.pdf 2>&1
    mmdc -i ARCHITECTURE_DIAGRAMS.md -o architecture_diagrams.png 2>&1
    echo "✓ Mermaid diagrams generated"
else
    echo "⚠ Mermaid CLI not found. Install with: npm install -g @mermaid-js/mermaid-cli"
    echo "  Or view diagrams online at: https://mermaid.live"
fi

echo ""
echo "Diagram generation complete!"
echo ""
echo "Generated files:"
echo "  - database_schema.png (if graphviz installed)"
echo "  - database_detailed.png (if graphviz installed)"
echo "  - architecture_diagrams.png (if mermaid-cli installed)"
echo ""
echo "View Mermaid diagrams:"
echo "  - Online: https://mermaid.live"
echo "  - VS Code: Install 'Markdown Preview Mermaid Support'"
echo "  - GitHub: Diagrams render automatically in markdown"
