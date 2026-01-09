# How to Apply Migration 0027 Without Render Shell Access

Since you can't access Render's shell, here are **automatic solutions** that will apply the migration when you deploy:

## ✅ Solution 1: Automatic on Startup (RECOMMENDED)

**What I've done:**
- Modified `store/wsgi.py` to automatically check and apply migration 0027 when the app starts
- Created `startup_migration_check.py` that safely applies the migration if needed

**How it works:**
1. When Render starts your app, `wsgi.py` runs
2. It checks if the `idempotency_key` column exists
3. If not, it automatically applies the migration
4. This happens **every time the app starts** (but it's safe - it checks first)

**What you need to do:**
1. **Commit and push** the updated files:
   ```bash
   git add store/wsgi.py startup_migration_check.py
   git commit -m "Add automatic migration 0027 check on startup"
   git push
   ```

2. **Wait for Render to deploy** - the migration will be applied automatically on the next deployment/restart

3. **Verify it worked** - check your Render logs for:
   ```
   ✅ Migration 0027 already applied - idempotency_key column exists
   ```
   or
   ```
   ✅ Migration 0027 applied successfully via management command
   ```

## ✅ Solution 2: Automatic During Build

**What I've done:**
- Modified `build.sh` to specifically check and apply migration 0027 during the build process

**How it works:**
1. During Render's build, `build.sh` runs
2. After running normal migrations, it specifically checks migration 0027
3. If not applied, it runs the management command to apply it

**What you need to do:**
1. **Commit and push** the updated `build.sh`:
   ```bash
   git add build.sh
   git commit -m "Add migration 0027 check to build script"
   git push
   ```

2. **Trigger a new deployment** on Render (or wait for next auto-deploy)

## ✅ Solution 3: Manual API Endpoint (Backup)

If the automatic methods don't work, you can create a one-time API endpoint to trigger the migration:

**Create this file:** `inventory/views.py` (add this view)

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsSuperuser
from rest_framework.response import Response
from rest_framework import status
from django.core.management import call_command

@api_view(['POST'])
@permission_classes([IsSuperuser])
def apply_migration_0027(request):
    """
    Admin-only endpoint to manually apply migration 0027.
    Only accessible to superusers.
    """
    try:
        call_command('apply_idempotency_migration')
        return Response({
            'success': True,
            'message': 'Migration 0027 applied successfully'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
```

Then add to `inventory/urls.py`:
```python
from .views import apply_migration_0027

urlpatterns = [
    # ... existing patterns ...
    path('admin/apply-migration-0027/', apply_migration_0027, name='apply-migration-0027'),
]
```

**To use:**
1. Get your superuser auth token
2. Make a POST request:
   ```bash
   curl -X POST https://your-render-app.onrender.com/api/inventory/admin/apply-migration-0027/ \
     -H "Authorization: Token YOUR_SUPERUSER_TOKEN"
   ```

## 🎯 Recommended Approach

**Use Solution 1 (Automatic on Startup)** because:
- ✅ Happens automatically - no manual intervention needed
- ✅ Safe - checks if migration is already applied
- ✅ Works on every deployment/restart
- ✅ No shell access required
- ✅ Already implemented and ready to deploy

## 📋 Steps to Apply

1. **Commit the changes:**
   ```bash
   git add store/wsgi.py startup_migration_check.py build.sh
   git commit -m "Add automatic migration 0027 application"
   git push
   ```

2. **Wait for Render to deploy** (or trigger manual deployment)

3. **Check Render logs** to confirm migration was applied:
   - Go to Render dashboard → Your service → Logs
   - Look for: `✅ Migration 0027 applied successfully` or `✅ Migration 0027 already applied`

4. **Test order creation** - it should now work with idempotency support

## 🔍 Verification

After deployment, you can verify the migration was applied by checking your Render logs or by testing order creation. The code will now:
- ✅ Work with or without the migration (graceful degradation)
- ✅ Automatically apply the migration on startup if missing
- ✅ Enable full idempotency once migration is applied

## ❓ Why Can't You Apply Migrations Locally?

When you run `python manage.py migrate` locally, it only affects your **local database**. Render has a **separate production database** that needs its own migrations applied. That's why we need these automatic solutions to apply the migration on Render's infrastructure.
