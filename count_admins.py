#!/usr/bin/env python3
"""
Quick script to count admin users.
Can be run with: python manage.py shell < count_admins.py
Or: python manage.py shell, then paste the code
"""
import os
import sys
import django

# Setup Django
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'store.settings')
    django.setup()

from django.contrib.auth import get_user_model
from inventory.models import Admin

User = get_user_model()

print("="*70)
print("ADMIN USER COUNT")
print("="*70)

# Count admins with Admin profile
admins_with_profile = Admin.objects.select_related('user').all()
admin_count = admins_with_profile.count()

# Count staff users (potential admins)
staff_users = User.objects.filter(is_staff=True)
staff_count = staff_users.count()

# Count superusers
superusers = User.objects.filter(is_superuser=True)
superuser_count = superusers.count()

# Count staff users without Admin profile
staff_without_admin = User.objects.filter(is_staff=True).exclude(admin__isnull=False)
staff_without_admin_count = staff_without_admin.count()

print(f"\n📊 Summary:")
print(f"   Total Admin Profiles: {admin_count}")
print(f"   Total Staff Users: {staff_count}")
print(f"   Total Superusers: {superuser_count}")
print(f"   Staff without Admin Profile: {staff_without_admin_count}")

if admin_count > 0:
    print(f"\n📋 Admin Users Details:")
    print("-" * 70)
    for idx, admin in enumerate(admins_with_profile, 1):
        user = admin.user
        print(f"\n{idx}. {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Admin Code: {admin.admin_code}")
        print(f"   is_staff: {user.is_staff}")
        print(f"   is_superuser: {user.is_superuser}")
        print(f"   is_active: {user.is_active}")
        
        # Check roles
        roles = admin.roles.all()
        if roles.exists():
            role_names = ', '.join([role.name for role in roles])
            print(f"   Roles: {role_names}")
        else:
            print(f"   Roles: None")

if staff_without_admin_count > 0:
    print(f"\n⚠️  Staff Users without Admin Profile:")
    print("-" * 70)
    for idx, user in enumerate(staff_without_admin, 1):
        print(f"{idx}. {user.username} ({user.email})")

print("\n" + "="*70)
print(f"✅ Total Admin Users (with Admin profile): {admin_count}")
print("="*70)
