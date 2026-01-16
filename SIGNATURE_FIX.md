# Fix for Cloudinary Signature Error

## Progress! ✅

**Cloudinary storage IS now being used!** The error shows it's trying to upload to Cloudinary.

## Issue: Invalid Signature Error

```
cloudinary.exceptions.Error: Invalid Signature
String to sign - 'folder=media/promotions/2026/01&tags=media&timestamp=1768564820&use_filename=1'
```

### The Problem

`MediaCloudinaryStorage` reads credentials from `settings.CLOUDINARY_STORAGE` dict when it's instantiated. If the dict doesn't have the correct API secret, it generates wrong signatures.

### The Fix Applied

1. **In `save()` method, ensure `CLOUDINARY_STORAGE` dict is set correctly:**
   ```python
   settings.CLOUDINARY_STORAGE = {
       'CLOUD_NAME': cloud_name,
       'API_KEY': api_key,
       'API_SECRET': api_secret,  # Must match Render environment variable!
       'SECURE': True,
       'RESOURCE_TYPE': 'auto',
   }
   ```

2. **Configure Cloudinary before setting storage:**
   ```python
   cloudinary.config(
       cloud_name=cloud_name,
       api_key=api_key,
       api_secret=api_secret,
       secure=True
   )
   ```

3. **Set storage on the field:**
   ```python
   banner_field.storage = MediaCloudinaryStorage()
   ```

This ensures:
- `CLOUDINARY_STORAGE` dict has correct credentials
- Cloudinary is configured before storage is used
- Storage instance reads from the correct dict

## Why This Should Work

- The storage reads from `settings.CLOUDINARY_STORAGE['API_SECRET']`
- We ensure the dict has the correct secret from environment variables
- Cloudinary is configured before the storage generates signatures

## Next Steps

1. **Deploy this fix**
2. **Test upload** - signature error should be fixed
3. **Check Cloudinary dashboard** - `promotions` folder should appear

The fix ensures the storage uses the correct API secret from Render environment variables!
