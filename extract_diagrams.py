#!/usr/bin/env python3
"""
Extract all Mermaid diagrams from markdown files and save them as individual .mmd files
"""

import re
import os
from pathlib import Path

def extract_mermaid_diagrams(markdown_file, output_dir):
    """Extract all mermaid code blocks from a markdown file"""
    if not os.path.exists(markdown_file):
        print(f"⚠️  File not found: {markdown_file}")
        return 0
    
    with open(markdown_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find all mermaid code blocks - match ```mermaid ... ```
    pattern = r'```mermaid\s*\n(.*?)\n```'
    matches = re.findall(pattern, content, re.DOTALL)
    
    if not matches:
        print(f"  ⚠️  No diagrams found in {os.path.basename(markdown_file)}")
        return 0
    
    basename = Path(markdown_file).stem
    count = 0
    
    for i, diagram in enumerate(matches, 1):
        # Clean up the diagram content
        diagram = diagram.strip()
        if not diagram:
            continue
            
        # Create output filename
        output_file = os.path.join(output_dir, f"{basename}_diagram_{i:02d}.mmd")
        
        # Write diagram to file
        with open(output_file, 'w', encoding='utf-8') as out:
            out.write(diagram)
        
        count += 1
    
    print(f"  ✅ Extracted {count} diagram(s) from {os.path.basename(markdown_file)}")
    return count

def main():
    print("==========================================")
    print("  Extract All Mermaid Diagrams")
    print("==========================================")
    print("")
    
    # Setup directories
    backend_dir = Path(__file__).parent.absolute()
    frontend_dir = backend_dir.parent / "affordable-gadgets-frontend"
    output_dir = backend_dir / "exported_diagrams" / "mermaid_files"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("📊 Extracting diagrams from markdown files...")
    print("")
    
    total = 0
    
    # Backend files
    backend_files = [
        backend_dir / "ARCHITECTURE_DIAGRAMS.md",
        backend_dir / "SERVICES_DETAILED.md",
        backend_dir / "API_ENDPOINTS_REFERENCE.md",
        backend_dir / "ARCHITECTURE_INDEX.md",
    ]
    
    for md_file in backend_files:
        if md_file.exists():
            total += extract_mermaid_diagrams(str(md_file), str(output_dir))
    
    # Frontend file
    frontend_file = frontend_dir / "FRONTEND_ARCHITECTURE.md"
    if frontend_file.exists():
        total += extract_mermaid_diagrams(str(frontend_file), str(output_dir))
    
    print("")
    print("==========================================")
    print(f"✅ Extraction complete! Total: {total} diagrams")
    print("")
    print(f"📁 Diagrams saved to: {output_dir}")
    print("")
    print("💡 Next steps:")
    print("   1. Install Mermaid CLI: npm install -g @mermaid-js/mermaid-cli")
    print("   2. Or use online: https://mermaid.live")
    print("   3. Copy any .mmd file content and paste into editor")
    print("   4. Download as PNG/SVG")
    print("==========================================")

if __name__ == "__main__":
    main()
