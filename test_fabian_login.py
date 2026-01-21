#!/usr/bin/env python
"""
Test script to check Fabian's login credentials and status.
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

def test_fabian_login():
    """Test Fabian's login credentials."""
    email = "fabian@shwariphones.com"
    password = "00000000"
    
    print("="*70)
    print("TESTING FABIAN'S LOGIN")
    print("="*70)
    
    # Check if user exists
    try:
        user = User.objects.get(email__iexact=email)
        print(f"\n✅ User found:")
        print(f"   Username: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   ID: {user.id}")
        print(f"   is_active: {user.is_active}")
        print(f"   is_staff: {user.is_staff}")
        print(f"   is_superuser: {user.is_superuser}")
        
        # Check admin profile
        try:
            admin = Admin.objects.get(user=user)
            print(f"   Admin Profile: EXISTS (admin_code: {admin.admin_code})")
        except Admin.DoesNotExist:
            print(f"   Admin Profile: MISSING")
        
        # Test Django authentication
        print(f"\n{'='*70}")
        print("TESTING DJANGO AUTHENTICATION")
        print("="*70)
        authenticated_user = authenticate(username=user.username, password=password)
        if authenticated_user:
            print(f"✅ Django authentication SUCCESS")
        else:
            print(f"❌ Django authentication FAILED - Invalid password")
            return False
        
        # Test serializer
        print(f"\n{'='*70}")
        print("TESTING AdminAuthTokenSerializer")
        print("="*70)
        
        # Try with email
        serializer_email = AdminAuthTokenSerializer(data={
            'username': email,
            'password': password
        })
        
        if serializer_email.is_valid():
            print(f"✅ Serializer validation SUCCESS (with email)")
            validated_user = serializer_email.validated_data['user']
            print(f"   Authenticated user: {validated_user.username}")
            print(f"   is_staff: {validated_user.is_staff}")
            print(f"   is_superuser: {validated_user.is_superuser}")
        else:
            print(f"❌ Serializer validation FAILED (with email)")
            print(f"   Errors: {serializer_email.errors}")
            return False
        
        # Try with username
        serializer_username = AdminAuthTokenSerializer(data={
            'username': user.username,
            'password': password
        })
        
        if serializer_username.is_valid():
            print(f"✅ Serializer validation SUCCESS (with username)")
        else:
            print(f"❌ Serializer validation FAILED (with username)")
            print(f"   Errors: {serializer_username.errors}")
        
        # Check token
        print(f"\n{'='*70}")
        print("CHECKING AUTH TOKEN")
        print("="*70)
        try:
            token = Token.objects.get(user=user)
            print(f"✅ Token exists: {token.key[:20]}...")
        except Token.DoesNotExist:
            print(f"⚠️  Token does not exist (will be created on login)")
        
        # Final status
        print(f"\n{'='*70}")
        print("FINAL STATUS")
        print("="*70)
        if user.is_staff or user.is_superuser:
            print(f"✅ User CAN login via AdminTokenLoginView")
            print(f"   Reason: User has is_staff={user.is_staff} or is_superuser={user.is_superuser}")
        else:
            print(f"❌ User CANNOT login via AdminTokenLoginView")
            print(f"   Reason: User does not have is_staff=True")
            print(f"\n   FIX: Set is_staff=True for this user")
            print(f"   Run: user.is_staff = True; user.save()")
            return False
        
        return True
        
    except User.DoesNotExist:
        print(f"\n❌ User not found with email: {email}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_fabian_login()
    sys.exit(0 if success else 1)
