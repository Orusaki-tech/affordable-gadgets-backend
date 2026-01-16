#!/usr/bin/env python3
"""
Verify that the Cloudinary credentials in Render match what's in Cloudinary dashboard.
"""
print("=" * 80)
print("CREDENTIALS VERIFICATION")
print("=" * 80)

# Values from Render (from your screenshot)
render_cloud_name = "dhgaqa2gb"
render_api_key = "428511131769392"
render_api_secret = "inHa4tnZC0znEW_hynKzcF0XFr4"

# Values you're asking about
user_secret = "inHa4tnZCOznEW_hynKzcF0XFr4"

print("\n📋 Values from Render Dashboard:")
print(f"   CLOUDINARY_CLOUD_NAME: {render_cloud_name}")
print(f"   CLOUDINARY_API_KEY: {render_api_key}")
print(f"   CLOUDINARY_API_SECRET: {render_api_secret}")

print("\n📋 Value you're checking:")
print(f"   API_SECRET: {user_secret}")

print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)

# Compare character by character
if render_api_secret == user_secret:
    print("✅ VALUES MATCH EXACTLY!")
    print("   Render and your value are identical")
else:
    print("❌ VALUES DO NOT MATCH!")
    print("\n   Differences found:")
    
    # Find differences
    min_len = min(len(render_api_secret), len(user_secret))
    differences = []
    
    for i in range(min_len):
        if render_api_secret[i] != user_secret[i]:
            differences.append(f"   Position {i}: Render='{render_api_secret[i]}' vs Your='{user_secret[i]}'")
    
    if len(render_api_secret) != len(user_secret):
        differences.append(f"   Length: Render={len(render_api_secret)} vs Your={len(user_secret)}")
    
    for diff in differences:
        print(diff)
    
    print("\n   ⚠️  These need to match exactly!")
    print("   Check for:")
    print("   - Zero (0) vs Letter O")
    print("   - Capital vs lowercase letters")
    print("   - Extra/missing characters")

print("\n" + "=" * 80)
print("RECOMMENDATION")
print("=" * 80)

if render_api_secret == user_secret:
    print("✅ Use the value from Render: inHa4tnZC0znEW_hynKzcF0XFr4")
    print("✅ This matches what you have")
else:
    print("⚠️  Use the EXACT value from Render dashboard")
    print("   Copy it directly from Render (don't type it)")
    print("   Render value: inHa4tnZC0znEW_hynKzcF0XFr4")

print("\n💡 To verify in Cloudinary:")
print("   1. Go to Cloudinary dashboard → API Keys")
print("   2. Find the 'Root' API key")
print("   3. Click 'Reveal' on the API Secret")
print("   4. Compare with Render value")
print("=" * 80)
