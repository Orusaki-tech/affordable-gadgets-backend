"""Management command to create superuser from environment variables (for deployment)."""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from inventory.models import Admin

User = get_user_model()


class Command(BaseCommand):
    help = 'Create superuser from environment variables (for deployment)'

    def handle(self, *args, **options):
        # Get credentials from environment variables with defaults
        username = os.environ.get('SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('SUPERUSER_EMAIL', 'affordablegadgetske@gmail.com')
        password = os.environ.get('SUPERUSER_PASSWORD', '6foot7foot')
        admin_code = os.environ.get('SUPERUSER_ADMIN_CODE', 'admin001')
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
            # Update password if it's different (in case it was changed)
            if not user.check_password(password):
                user.set_password(password)
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Updated password for existing superuser "{username}"')
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(f'Superuser "{username}" already exists. Skipping creation.')
                )
            
            # Ensure Admin profile exists
            admin, created = Admin.objects.get_or_create(
                user=user,
                defaults={'admin_code': admin_code}
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Created Admin profile for existing user "{username}"')
                )
            
            # Ensure user is superuser and staff
            if not user.is_superuser or not user.is_staff:
                user.is_superuser = True
                user.is_staff = True
                user.save()
                self.stdout.write(
                    self.style.SUCCESS(f'Updated user "{username}" to superuser and staff status')
                )
            
            return
        
        try:
            # Create superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            
            # Create admin profile
            Admin.objects.create(
                user=user,
                admin_code=admin_code
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Created superuser successfully!\n'
                    f'   Username: {username}\n'
                    f'   Email: {email}\n'
                    f'   Admin Code: {admin_code}\n'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create superuser: {e}')
            )
            # Don't raise - allow deployment to continue even if superuser creation fails
            return

