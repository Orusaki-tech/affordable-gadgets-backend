#!/usr/bin/env python
"""
Test script to diagnose and test admin login API.
Can be run with: python manage.py shell < test_admin_login_api.py
Or: python manage.py shell, then paste the code
"""
import os
import sys
import django

# Setup Django
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
    django.setup()

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import User
from inventory.models import Admin
from rest_framework.authtoken.models import Token
from inventory.serializers import AdminAuthTokenSerializer

User = get_user_model()

def check_all_admin_users():
    """Check status of all admin users."""
    print("="*70)
    print("CHECKING ALL ADMIN USERS")
    print("="*70)
    
    # Get all users with Admin profiles
    admin_profiles = Admin.objects.select_related('user').all()
    
    if admin_profiles.count() == 0:
        print("\n❌ No admin users found!")
        return []
    
    admin_users = []
    for admin in admin_profiles:
        user = admin.user
        if user:
            admin_users.append({
                'user': user,
                'admin': admin,
                'username': user.username,
                'email': user.email,
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'is_superuser': user.is_superuser,
            })
    
    # Also check staff users without admin profiles
    staff_users = User.objects.filter(is_staff=True).exclude(admin__isnull=False)
    for user in staff_users:
        admin_users.append({
            'user': user,
            'admin': None,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        })
    
    print(f"\nFound {len(admin_users)} admin/staff user(s):\n")
    
    for idx, admin_info in enumerate(admin_users, 1):
        user = admin_info['user']
        admin = admin_info['admin']
        
        print(f"{idx}. Username: {admin_info['username']}")
        print(f"   Email: {admin_info['email']}")
        print(f"   is_active: {admin_info['is_active']}")
        print(f"   is_staff: {admin_info['is_staff']}")
        print(f"   is_superuser: {admin_info['is_superuser']}")
        print(f"   Admin Profile: {'EXISTS' if admin else 'MISSING'}")
        if admin:
            print(f"   Admin Code: {admin.admin_code}")
        
        # Check token
        try:
            token = Token.objects.get(user=user)
            print(f"   Token: EXISTS")
        except Token.DoesNotExist:
            print(f"   Token: MISSING")
        
        # Check if user can authenticate (without password check)
        if not admin_info['is_staff'] and not admin_info['is_superuser']:
            print(f"   ⚠️  WARNING: User does not have is_staff=True!")
            print(f"      This user will NOT be able to login via AdminTokenLoginView")
        
        print()
    
    return admin_users

def test_serializer(username_or_email, password):
    """Test the AdminAuthTokenSerializer."""
    print("="*70)
    print(f"TESTING AdminAuthTokenSerializer")
    print(f"Username/Email: {username_or_email}")
    print("="*70)
    
    serializer = AdminAuthTokenSerializer(data={
        'username': username_or_email,
        'password': password
    })
    
    if serializer.is_valid():
        user = serializer.validated_data['user']
        print(f"\n✅ Serializer validation SUCCESS")
        print(f"   Authenticated user: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   is_staff: {user.is_staff}")
        print(f"   is_superuser: {user.is_superuser}")
        return True
    else:
        print(f"\n❌ Serializer validation FAILED")
        print(f"   Errors: {serializer.errors}")
        return False

def fix_missing_staff_flag():
    """Fix admin users that don't have is_staff=True."""
    print("="*70)
    print("FIXING MISSING is_staff FLAGS")
    print("="*70)
    
    # Find admin users without is_staff=True
    admin_profiles = Admin.objects.select_related('user').filter(user__is_staff=False)
    
    if admin_profiles.count() == 0:
        print("\n✅ All admin users have is_staff=True")
        return
    
    print(f"\nFound {admin_profiles.count()} admin user(s) without is_staff=True:")
    
    for admin in admin_profiles:
        user = admin.user
        if user:
            print(f"\n  Fixing: {user.username} (ID: {user.id})")
            user.is_staff = True
            user.save()
            print(f"  ✅ Set is_staff=True for {user.username}")

if __name__ == '__main__':
    print("\n" + "="*70)
    print("ADMIN LOGIN DIAGNOSTIC TOOL")
    print("="*70 + "\n")
    
    # Check all admin users
    admin_users = check_all_admin_users()
    
    # Fix missing staff flags
    fix_missing_staff_flag()
    
    # If admin users were fixed, check again
    if admin_users:
        print("\n" + "="*70)
        print("RE-CHECKING AFTER FIXES")
        print("="*70)
        check_all_admin_users()
    
    print("\n" + "="*70)
    print("TESTING INSTRUCTIONS")
    print("="*70)
    print("""
To test login with a specific user, run:
    
    from inventory.serializers import AdminAuthTokenSerializer
    serializer = AdminAuthTokenSerializer(data={
        'username': 'username_or_email',
        'password': 'password'
    })
    serializer.is_valid()
    print(serializer.errors if not serializer.is_valid() else "Success!")
    
Or test via API:
    curl -X POST http://localhost:8000/api/auth/token/login/ \\
         -H "Content-Type: application/x-www-form-urlencoded" \\
         -d "username=username_or_email&password=password"
    """)
