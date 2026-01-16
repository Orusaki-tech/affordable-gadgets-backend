# How to Find Cloudinary Credentials

## Required Credentials

You need **3 credentials** from Cloudinary:

1. **CLOUDINARY_CLOUD_NAME** - Your cloud name (e.g., `dhgaqa2gb`)
2. **CLOUDINARY_API_KEY** - Your API key (e.g., `428511131769392`)
3. **CLOUDINARY_API_SECRET** - Your API secret (e.g., `inHa4tnZC0znEW_hynKzcF0XFr4`)

## Step-by-Step: Finding Your Credentials

### Method 1: Dashboard (Easiest)

1. **Log in to Cloudinary:**
   - Go to: https://console.cloudinary.com/
   - Log in with your account

2. **Go to Dashboard:**
   - Once logged in, you'll see your dashboard
   - Look at the top of the page - your **Cloud Name** is displayed there
   - Example: `dhgaqa2gb` (this is your `CLOUDINARY_CLOUD_NAME`)

3. **Find API Credentials:**
   - Click on your **profile/account icon** (usually top right)
   - Select **"Settings"** or **"Account Settings"**
   - OR go directly to: https://console.cloudinary.com/settings/account
   
4. **View API Credentials:**
   - Scroll down to the **"API Keys"** section
   - You'll see:
     - **API Key**: A long number (e.g., `428511131769392`)
     - **API Secret**: Click "Reveal" to show it (e.g., `inHa4tnZC0znEW_hynKzcF0XFr4`)
   
5. **Copy the values:**
   - **Cloud Name**: Already visible (e.g., `dhgaqa2gb`)
   - **API Key**: Copy the number
   - **API Secret**: Click "Reveal" and copy it

### Method 2: Dashboard URL

Your Cloudinary dashboard URL contains your cloud name:
- URL format: `https://console.cloudinary.com/console/c-XXXXX/`
- The `c-XXXXX` part is your cloud identifier
- But the **Cloud Name** is usually shown in the dashboard header

### Method 3: From Environment Variables (If Already Set)

If credentials are already set somewhere, check:

1. **Render Dashboard:**
   - Go to your Render service
   - Click "Environment"
   - Look for `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`

2. **Local `.env` file:**
   - Check if you have a `.env` file in your project
   - Look for the same variable names

## Your Current Credentials (Based on Previous Tests)

Based on what we've seen in your setup:

```
CLOUDINARY_CLOUD_NAME=dhgaqa2gb
CLOUDINARY_API_KEY=428511131769392
CLOUDINARY_API_SECRET=inHa4tnZC0znEW_hynKzcF0XFr4
```

**⚠️ Important:** These should match what's in your Cloudinary dashboard. If they don't, use the values from your dashboard.

## Where to Set These Credentials

### In Render (Production):

1. Go to: https://dashboard.render.com/
2. Select your backend service: `affordable-gadgets-backend`
3. Click **"Environment"** in the left sidebar
4. Add/Edit these environment variables:
   - `CLOUDINARY_CLOUD_NAME` = `dhgaqa2gb` (or your actual cloud name)
   - `CLOUDINARY_API_KEY` = `428511131769392` (or your actual API key)
   - `CLOUDINARY_API_SECRET` = `inHa4tnZC0znEW_hynKzcF0XFr4` (or your actual secret)
5. Click **"Save Changes"**
6. **Redeploy** your service (Render will auto-deploy or you can trigger manually)

### For Local Development:

Create a `.env` file in your project root:

```env
CLOUDINARY_CLOUD_NAME=dhgaqa2gb
CLOUDINARY_API_KEY=428511131769392
CLOUDINARY_API_SECRET=inHa4tnZC0znEW_hynKzcF0XFr4
```

## Security Notes

- ⚠️ **Never commit API secrets to Git**
- ✅ Add `.env` to `.gitignore`
- ✅ Use environment variables in production
- ✅ API Secret should be kept private

## Verification

After setting credentials:

1. **Check Render logs** after deployment:
   - Should see: `✅ CLOUDINARY CONFIGURED: cloud=dhgaqa2gb...`
   - Should see: `✅ CLOUDINARY STORAGE ENABLED: Using MediaCloudinaryStorage`

2. **Test upload:**
   - Upload an image via admin
   - Check Cloudinary dashboard → Media Library
   - Should see `promotions` folder appear

## Troubleshooting

### "Credentials Missing" Error:
- Check that all 3 variables are set in Render
- Verify no typos in variable names (case-sensitive)
- Make sure values don't have extra spaces

### "Invalid Credentials" Error:
- Verify credentials match your Cloudinary dashboard
- Check if API key/secret are correct
- Ensure you're using the Root API key (not a restricted one)

### Still Not Working:
- Check Render logs for specific error messages
- Verify credentials are set before deployment
- Try regenerating API secret in Cloudinary dashboard
