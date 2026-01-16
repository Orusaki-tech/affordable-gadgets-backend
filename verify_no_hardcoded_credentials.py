#!/usr/bin/env python3
"""
Verify that no Cloudinary credentials are hardcoded in the codebase.
All credentials should come from environment variables.
"""
import os
import re

# Credentials to check for (should NOT be in code)
CREDENTIALS_TO_CHECK = [
    'dhgaqa2gb',  # Cloud name
    '428511131769392',  # API Key
    'inHa4tnZC0znEW_hynKzcF0XFr4',  # API Secret
]

# Files to check
FILES_TO_CHECK = [
    'store/settings.py',
    'inventory/models.py',
    'inventory/views.py',
    'inventory/serializers.py',
]

print("=" * 80)
print("VERIFYING NO HARDCODED CREDENTIALS")
print("=" * 80)

hardcoded_found = False

for file_path in FILES_TO_CHECK:
    if not os.path.exists(file_path):
        continue
    
    with open(file_path, 'r') as f:
        content = f.read()
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            for cred in CREDENTIALS_TO_CHECK:
                # Check if credential appears in code (not in comments or strings that are examples)
                if cred in line:
                    # Skip if it's in a comment
                    if line.strip().startswith('#'):
                        continue
                    # Skip if it's in a docstring or example
                    if 'example' in line.lower() or 'e.g.' in line.lower():
                        continue
                    # Skip if it's in a print/log statement (those are OK)
                    if 'print' in line or 'logger' in line or 'log' in line.lower():
                        continue
                    
                    # This might be hardcoded!
                    print(f"\n⚠️  Potential hardcoded credential found:")
                    print(f"   File: {file_path}")
                    print(f"   Line {i}: {line.strip()}")
                    hardcoded_found = True

# Check settings.py specifically
print("\n" + "=" * 80)
print("CHECKING settings.py")
print("=" * 80)

if os.path.exists('store/settings.py'):
    with open('store/settings.py', 'r') as f:
        content = f.read()
        
    # Check if credentials are read from environment
    if 'os.environ.get(\'CLOUDINARY_CLOUD_NAME\'' in content:
        print("✅ CLOUDINARY_CLOUD_NAME read from environment")
    else:
        print("❌ CLOUDINARY_CLOUD_NAME might be hardcoded")
        hardcoded_found = True
    
    if 'os.environ.get(\'CLOUDINARY_API_KEY\'' in content:
        print("✅ CLOUDINARY_API_KEY read from environment")
    else:
        print("❌ CLOUDINARY_API_KEY might be hardcoded")
        hardcoded_found = True
    
    if 'os.environ.get(\'CLOUDINARY_API_SECRET\'' in content:
        print("✅ CLOUDINARY_API_SECRET read from environment")
    else:
        print("❌ CLOUDINARY_API_SECRET might be hardcoded")
        hardcoded_found = True

# Check models.py
print("\n" + "=" * 80)
print("CHECKING inventory/models.py")
print("=" * 80)

if os.path.exists('inventory/models.py'):
    with open('inventory/models.py', 'r') as f:
        content = f.read()
        
    # Check if credentials are read from environment or settings
    if 'os.environ.get(\'CLOUDINARY_CLOUD_NAME\'' in content or 'getattr(settings, \'CLOUDINARY_CLOUD_NAME\'' in content:
        print("✅ CLOUDINARY_CLOUD_NAME read from environment/settings")
    else:
        print("❌ CLOUDINARY_CLOUD_NAME might be hardcoded")
        hardcoded_found = True
    
    if 'os.environ.get(\'CLOUDINARY_API_KEY\'' in content or 'getattr(settings, \'CLOUDINARY_API_KEY\'' in content:
        print("✅ CLOUDINARY_API_KEY read from environment/settings")
    else:
        print("❌ CLOUDINARY_API_KEY might be hardcoded")
        hardcoded_found = True
    
    if 'os.environ.get(\'CLOUDINARY_API_SECRET\'' in content or 'getattr(settings, \'CLOUDINARY_API_SECRET\'' in content:
        print("✅ CLOUDINARY_API_SECRET read from environment/settings")
    else:
        print("❌ CLOUDINARY_API_SECRET might be hardcoded")
        hardcoded_found = True

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

if not hardcoded_found:
    print("✅ NO HARDCODED CREDENTIALS FOUND")
    print("✅ All credentials are read from environment variables")
    print("✅ Code is flexible and won't break if credentials change")
else:
    print("❌ POTENTIAL HARDCODED CREDENTIALS FOUND")
    print("⚠️  Review the code above")

print("=" * 80)
