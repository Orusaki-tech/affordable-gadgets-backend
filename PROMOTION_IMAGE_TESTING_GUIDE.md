# Promotion Image Testing Guide

## Current Status
- ✅ Cloudinary configuration is correct
- ✅ Promotion serializer has image handling logic
- ❌ No promotions found in database (or no active promotions)
- ❌ Need to test with proper brand header

## How to Test Promotion Images

### Step 1: Create a Test Promotion via Admin

1. **Go to Admin Interface**
   - URL: https://affordable-gadgets-admin.vercel.app/
   - Log in as admin

2. **Navigate to Promotions**
   - Find the Promotions section in the admin panel

3. **Create a New Promotion**
   - Click "Create Promotion" or "Add Promotion"
   - Fill in required fields:
     - **Title**: "Test Promotion"
     - **Description**: "Testing image upload"
     - **Brand**: Select a brand (required)
     - **Start Date**: Set to today or past date
     - **End Date**: Set to future date (e.g., 30 days from now)
     - **Is Active**: Check this box
     - **Display Locations**: Select at least one (e.g., "stories_carousel")

4. **Upload Banner Image**
   - Find the "Banner Image" field
   - Click "Choose File" or drag and drop an image
   - Select an image file (JPG, PNG, etc.)
   - **Important**: The image should upload to Cloudinary automatically if credentials are set

5. **Save the Promotion**
   - Click "Save" or "Create"
   - Note the promotion ID

### Step 2: Verify Image Upload

#### Option A: Check Cloudinary Dashboard
1. Go to https://cloudinary.com/console
2. Log in to your Cloudinary account
3. Navigate to Media Library
4. Look for images in the `promotions/` folder
5. Verify the image was uploaded successfully

#### Option B: Test via API

Run this test script after creating a promotion:

```bash
python3 test_promotions_images.py
```

Or test manually with curl:

```bash
# Get brand code from your frontend config or admin
BRAND_CODE="your-brand-code"

# Test promotions API with brand header
curl -H "X-Brand-Code: $BRAND_CODE" \
  "https://affordable-gadgets-backend.onrender.com/api/v1/public/promotions/"
```

### Step 3: Expected Results

After uploading a promotion with an image, the API should return:

```json
{
  "results": [
    {
      "id": 1,
      "title": "Test Promotion",
      "banner_image": "https://res.cloudinary.com/[cloud-name]/image/upload/q_auto,f_auto/w_1080,h_1920,c_fill/promotions/2026/01/image_name",
      "banner_image_url": "https://res.cloudinary.com/[cloud-name]/image/upload/q_auto,f_auto/w_1080,h_1920,c_fill/promotions/2026/01/image_name",
      ...
    }
  ]
}
```

**Key indicators of success:**
- ✅ `banner_image` contains a URL
- ✅ URL starts with `https://res.cloudinary.com/`
- ✅ URL contains optimization parameters (`q_auto,f_auto`)
- ✅ URL contains transformation parameters (`w_1080,h_1920,c_fill`)

### Step 4: Verify on Frontend

1. **Check E-commerce Frontend**
   - URL: https://affordable-gadgets-front-git-97f0b9-affordable-gadgets-projects.vercel.app/
   - Navigate to pages that show promotions:
     - Stories Carousel (if `display_locations` includes "stories_carousel")
     - Special Offers section (if includes "special_offers")
   - Verify images display correctly

2. **Check Browser Console**
   - Open browser DevTools (F12)
   - Check Console for any image loading errors
   - Check Network tab to see if images load successfully

### Troubleshooting

#### Issue: Images not uploading to Cloudinary

**Check:**
1. Cloudinary credentials in Render environment variables:
   ```env
   CLOUDINARY_CLOUD_NAME=your-cloud-name
   CLOUDINARY_API_KEY=your-api-key
   CLOUDINARY_API_SECRET=your-api-secret
   ```
2. `DEFAULT_FILE_STORAGE` is set to `cloudinary_storage.storage.MediaCloudinaryStorage`
3. Check backend logs for Cloudinary errors

#### Issue: Images upload but URLs are local

**Possible causes:**
1. Images were uploaded before Cloudinary was configured
2. Cloudinary credentials are missing or incorrect
3. Storage backend not properly set

**Solution:**
- Re-upload images after verifying Cloudinary credentials
- Check that `DEFAULT_FILE_STORAGE` is correct in settings

#### Issue: Promotions API returns empty

**Check:**
1. Promotion is active (`is_active=True`)
2. Promotion dates are valid (start_date <= now <= end_date)
3. Brand header is sent (`X-Brand-Code: your-brand-code`)
4. Promotion is assigned to the correct brand

#### Issue: Images don't display on frontend

**Check:**
1. Next.js config allows Cloudinary images (`res.cloudinary.com`)
2. Image URLs are accessible (test with curl or browser)
3. CORS is configured correctly
4. Check browser console for errors

### Testing Checklist

- [ ] Created a test promotion via admin
- [ ] Uploaded banner image
- [ ] Verified image appears in Cloudinary dashboard
- [ ] Tested promotions API with brand header
- [ ] Confirmed `banner_image` URL is Cloudinary URL
- [ ] Verified image displays on frontend
- [ ] Checked browser console for errors
- [ ] Tested image accessibility (can load in browser)

### Next Steps After Testing

Once promotion images work:
1. Upload images for all active promotions
2. Test product images (same process)
3. Verify all images display correctly on both frontends
4. Monitor Cloudinary usage and optimize if needed
