# Fix for Cloudinary Signature Error

## Progress! ✅

**Cloudinary storage IS now being used!** The error shows it's trying to upload to Cloudinary.

## New Issue: Signature Error

```
cloudinary.exceptions.Error: Invalid Signature
String to sign - 'folder=media/promotions/2026/01&tags=media&timestamp=1768564045&use_filename=1'
```

### The Problem

When we instantiate `MediaCloudinaryStorage()` directly, it might not have the credentials properly configured. The storage needs to read from the `CLOUDINARY_STORAGE` dict, but when instantiated directly, it might not be reading it correctly.

### The Fix Applied

1. **Configure Cloudinary BEFORE creating storage instance:**
   ```python
   cloudinary.config(
       cloud_name=_cloud_name,
       api_key=_api_key,
       api_secret=_api_secret,
       secure=True
   )
   ```

2. **Then create storage instance:**
   ```python
   _promotion_banner_storage = MediaCloudinaryStorage()
   ```

This ensures Cloudinary is configured before the storage instance is created, so it can properly generate signatures.

## What Changed

- Added `cloudinary.config()` call before creating `MediaCloudinaryStorage()`
- This ensures credentials are available when the storage generates upload signatures

## Next Steps

1. **Deploy this fix**
2. **Test upload again** - signature error should be fixed
3. **Check Cloudinary dashboard** - `promotions` folder should appear

The fix ensures Cloudinary is properly configured before the storage instance is created!
