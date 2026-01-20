# Admin Login Fix

## Problem
Admin users (non-superuser) were unable to login via the admin panel. The login would fail even with correct credentials.

## Root Cause
The `AdminTokenLoginView` was using the default `ObtainAuthToken` view which uses `AuthTokenSerializer`. This serializer had two issues:

1. **No staff check**: It didn't verify that the user has `is_staff=True` before allowing login
2. **Email support**: While it accepted username, it didn't properly handle email-based login

After login, the frontend tries to retrieve the admin profile which requires `is_staff=True`. So even if login succeeded, the profile retrieval would fail, making it appear as if login failed.

## Solution
Created a custom `AdminAuthTokenSerializer` that:

1. **Supports email login**: Accepts username field that can contain either username or email
2. **Enforces staff status**: Checks that `user.is_staff=True` or `user.is_superuser=True` before allowing login
3. **Better error messages**: Provides clear error messages when login fails due to missing staff privileges

## Changes Made

### 1. `inventory/serializers.py`
- Added `AdminAuthTokenSerializer` class that extends `serializers.Serializer`
- Validates username/email and password
- Checks for `is_staff` or `is_superuser` status
- Returns appropriate error messages

### 2. `inventory/views.py`
- Updated `AdminTokenLoginView` to use `AdminAuthTokenSerializer` instead of default `AuthTokenSerializer`
- Added documentation about email support and staff requirement

## Testing

### Check Admin Users Status
Run the diagnostic script:
```bash
python manage.py shell < test_admin_login_api.py
```

Or interactively:
```python
python manage.py shell
>>> exec(open('test_admin_login_api.py').read())
```

### Test Login via API
```bash
# Test with username
curl -X POST http://localhost:8000/api/auth/token/login/ \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin_user&password=password"

# Test with email
curl -X POST http://localhost:8000/api/auth/token/login/ \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@example.com&password=password"
```

### Expected Behavior
- ✅ Users with `is_staff=True` or `is_superuser=True` can login
- ❌ Users without `is_staff=True` will get error: "This account does not have admin privileges..."
- ✅ Both username and email work for login
- ✅ Invalid credentials return: "Unable to log in with provided credentials."
- ✅ Inactive users return: "User account is disabled."

## Fixing Existing Admin Users

If you have admin users without `is_staff=True`, you can fix them:

```python
from django.contrib.auth import get_user_model
from inventory.models import Admin

User = get_user_model()

# Fix all admin users without is_staff=True
for admin in Admin.objects.select_related('user').filter(user__is_staff=False):
    if admin.user:
        admin.user.is_staff = True
        admin.user.save()
        print(f"Fixed: {admin.user.username}")
```

Or use the diagnostic script which includes an automatic fix function.

## Verification Checklist

- [ ] All admin users have `is_staff=True`
- [ ] Superuser can still login (backward compatibility)
- [ ] Regular admin users can login with username
- [ ] Regular admin users can login with email
- [ ] Non-staff users get appropriate error message
- [ ] Admin profile retrieval works after login
