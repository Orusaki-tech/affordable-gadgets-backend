#!/usr/bin/env python
"""
Test script to diagnose admin login issues.
Tests login for all admin users and checks their status.
"""
import os
import sys
import django
import requests
import json

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
django.setup()

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import User
from inventory.models import Admin
from rest_framework.authtoken.models import Token

User = get_user_model()

def check_user_status(user):
    """Check and print user status."""
    print(f"\n{'='*60}")
    print(f"User: {user.username}")
    print(f"Email: {user.email}")
    print(f"ID: {user.id}")
    print(f"is_active: {user.is_active}")
    print(f"is_staff: {user.is_staff}")
    print(f"is_superuser: {user.is_superuser}")
    print(f"last_login: {user.last_login}")
    
    # Check if user has Admin profile
    try:
        admin_profile = Admin.objects.get(user=user)
        print(f"Admin Profile: EXISTS (admin_code: {admin_profile.admin_code})")
        print(f"Admin Roles: {[role.name for role in admin_profile.roles.all()]}")
    except Admin.DoesNotExist:
        print(f"Admin Profile: DOES NOT EXIST")
    
    # Check if user has token
    try:
        token = Token.objects.get(user=user)
        print(f"Token: EXISTS ({token.key[:20]}...)")
    except Token.DoesNotExist:
        print(f"Token: DOES NOT EXIST")

def test_authentication(username, password):
    """Test Django authentication."""
    print(f"\n{'='*60}")
    print(f"Testing Django authentication for: {username}")
    user = authenticate(username=username, password=password)
    if user:
        print(f"✅ Authentication SUCCESS")
        print(f"   User: {user.username}")
        print(f"   is_active: {user.is_active}")
        print(f"   is_staff: {user.is_staff}")
        return user
    else:
        print(f"❌ Authentication FAILED")
        return None

def test_api_login(base_url, username, password):
    """Test API login endpoint."""
    print(f"\n{'='*60}")
    print(f"Testing API login for: {username}")
    url = f"{base_url}/api/auth/token/login/"
    
    data = {
        'username': username,
        'password': password
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"Response JSON: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            token = response_data.get('token')
            if token:
                print(f"✅ API Login SUCCESS - Token received")
                return token
            else:
                print(f"❌ API Login FAILED - No token in response")
                return None
        else:
            print(f"❌ API Login FAILED - Status {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ API Login ERROR: {str(e)}")
        return None

def test_admin_profile(base_url, token):
    """Test admin profile retrieval."""
    print(f"\n{'='*60}")
    print(f"Testing Admin Profile Retrieval")
    url = f"{base_url}/api/inventory/profiles/admin/"
    
    headers = {
        'Authorization': f'Token {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        try:
            response_data = response.json()
            print(f"Response JSON: {json.dumps(response_data, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            print(f"✅ Admin Profile Retrieval SUCCESS")
            return True
        else:
            print(f"❌ Admin Profile Retrieval FAILED - Status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Admin Profile Retrieval ERROR: {str(e)}")
        return False

def main():
    print("="*60)
    print("ADMIN LOGIN DIAGNOSTIC TEST")
    print("="*60)
    
    # Get base URL from environment or use default
    base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000')
    print(f"\nUsing API Base URL: {base_url}")
    
    # Get all staff users
    print(f"\n{'='*60}")
    print("FINDING ALL ADMIN USERS")
    print("="*60)
    
    staff_users = User.objects.filter(is_staff=True)
    admin_users = User.objects.filter(admin__isnull=False)
    all_admin_users = (staff_users | admin_users).distinct()
    
    print(f"\nTotal staff users: {staff_users.count()}")
    print(f"Total users with Admin profile: {admin_users.count()}")
    print(f"Total admin users (combined): {all_admin_users.count()}")
    
    if all_admin_users.count() == 0:
        print("\n❌ No admin users found!")
        return
    
    # Check each admin user
    print(f"\n{'='*60}")
    print("CHECKING USER STATUS")
    print("="*60)
    
    for user in all_admin_users:
        check_user_status(user)
    
    # Test login for each user (you'll need to provide passwords)
    print(f"\n{'='*60}")
    print("TESTING LOGIN")
    print("="*60)
    print("\nNote: This will test authentication but requires passwords.")
    print("To test API login, you'll need to provide passwords manually.")
    
    # Test with a specific user if provided
    test_username = os.environ.get('TEST_USERNAME')
    test_password = os.environ.get('TEST_PASSWORD')
    
    if test_username and test_password:
        print(f"\n{'='*60}")
        print(f"TESTING WITH PROVIDED CREDENTIALS")
        print("="*60)
        
        # Test Django authentication
        user = test_authentication(test_username, test_password)
        
        if user:
            check_user_status(user)
            
            # Test API login
            token = test_api_login(base_url, test_username, test_password)
            
            if token:
                # Test admin profile retrieval
                test_admin_profile(base_url, token)
        else:
            print(f"\n❌ Cannot proceed with API tests - Django authentication failed")
    else:
        print(f"\nTo test login, set environment variables:")
        print(f"  export TEST_USERNAME='username'")
        print(f"  export TEST_PASSWORD='password'")
        print(f"  export API_BASE_URL='http://localhost:8000'")
        print(f"\nThen run: python test_admin_login.py")

if __name__ == '__main__':
    main()
