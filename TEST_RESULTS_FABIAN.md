# Test Results for Fabian's Login

## API Endpoint Tested
- **URL**: `https://affordable-gadgets-backend.onrender.com/api/auth/token/login/`
- **Method**: POST
- **Content-Type**: `application/x-www-form-urlencoded`

## Test Credentials
- **Email**: `fabian@shwariphones.com`
- **Password**: `00000000`

## Test Results

### ✅ API Endpoint is Accessible
The API endpoint is responding correctly.

### ❌ Login Failed
**Response**: HTTP 400 Bad Request
**Error Message**: `{"non_field_errors":["Unable to log in with provided credentials."]}`

## Possible Causes

1. **User doesn't exist in production database**
   - The user `fabian@shwariphones.com` may not exist in the production database
   - Solution: Create the user or check if it exists

2. **Password is incorrect**
   - The password `00000000` may not match what's stored in the database
   - Solution: Reset the password or verify the correct password

3. **Email lookup issue**
   - The serializer might not be finding the user by email
   - Solution: Try logging in with the username instead of email

4. **User account is inactive**
   - The user account might have `is_active=False`
   - Solution: Check and activate the user account

5. **Database not synced**
   - Production database might not have the latest user data
   - Solution: Verify user exists in production database

## Next Steps

### 1. Check if user exists in production database

Run this Django management command on production:
```bash
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.filter(email='fabian@shwariphones.com').first()
>>> if user:
...     print(f"User found: {user.username}")
...     print(f"is_active: {user.is_active}")
...     print(f"is_staff: {user.is_staff}")
...     print(f"is_superuser: {user.is_superuser}")
... else:
...     print("User not found")
```

### 2. Try login with username instead of email

If you know the username, try:
```bash
curl -k -X POST https://affordable-gadgets-backend.onrender.com/api/auth/token/login/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=ACTUAL_USERNAME&password=00000000"
```

### 3. Create/Update user in production

If user doesn't exist or needs to be fixed:
```python
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> 
>>> # Check if user exists
>>> user = User.objects.filter(email='fabian@shwariphones.com').first()
>>> 
>>> if not user:
...     # Create user
...     user = User.objects.create_user(
...         username='fabian',  # or appropriate username
...         email='fabian@shwariphones.com',
...         password='00000000',
...         is_staff=True,
...         is_active=True
...     )
...     print(f"Created user: {user.username}")
... else:
...     # Update existing user
...     user.set_password('00000000')
...     user.is_staff = True
...     user.is_active = True
...     user.save()
...     print(f"Updated user: {user.username}")
>>> 
>>> # Create Admin profile if needed
>>> from inventory.models import Admin
>>> admin, created = Admin.objects.get_or_create(
...     user=user,
...     defaults={'admin_code': 'FABIAN001'}
... )
>>> print(f"Admin profile: {'created' if created else 'exists'}")
```

### 4. Test login again

After fixing the user, test login:
```bash
curl -k -X POST https://affordable-gadgets-backend.onrender.com/api/auth/token/login/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=fabian@shwariphones.com&password=00000000"
```

Expected success response:
```json
{"token": "abc123..."}
```

## Test Script

Use the provided test script:
```bash
python3 test_fabian_api.py https://affordable-gadgets-backend.onrender.com
```

Or use the bash script:
```bash
./test_api_login.sh https://affordable-gadgets-backend.onrender.com
```

## Notes

- The API endpoint is working correctly
- The authentication logic is functioning (it's rejecting invalid credentials)
- The issue is likely with the user data in the production database
- Once the user is properly set up in production, login should work
