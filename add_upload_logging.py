"""
Add logging to Promotion save to see what's happening with uploads.
This will help diagnose why images aren't actually uploading to Cloudinary.
"""
import os

# Read the views.py file to add logging
views_path = '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/inventory/views.py'

with open(views_path, 'r') as f:
    content = f.read()

# Check if logging is already there
if 'DEBUG: Banner image upload' in content:
    print("Logging already exists")
else:
    # Add logging after serializer.save()
    old_code = """        promotion_instance = serializer.save(created_by=admin)
        # #region agent log"""
    
    new_code = """        promotion_instance = serializer.save(created_by=admin)
        
        # DEBUG: Log banner image upload status
        import logging
        logger = logging.getLogger(__name__)
        if promotion_instance.banner_image:
            banner_url = promotion_instance.banner_image.url
            banner_name = promotion_instance.banner_image.name
            is_cloudinary = 'cloudinary.com' in banner_url.lower()
            logger.info(f"DEBUG: Banner image upload - URL: {banner_url}, Name: {banner_name}, IsCloudinary: {is_cloudinary}")
            print(f"DEBUG: Banner image upload - URL: {banner_url}, Name: {banner_name}, IsCloudinary: {is_cloudinary}")
        else:
            logger.info("DEBUG: No banner image after save")
            print("DEBUG: No banner image after save")
        
        # #region agent log"""
    
    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(views_path, 'w') as f:
            f.write(content)
        print("✅ Added logging to views.py")
    else:
        print("❌ Could not find insertion point")
