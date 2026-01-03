"""Management command to list admin users and their credentials."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from inventory.models import Admin

User = get_user_model()


class Command(BaseCommand):
    help = 'List all admin users with their credentials'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create',
            action='store_true',
            help='Create a new admin user if none exist'
        )

    def handle(self, *args, **options):
        admins = Admin.objects.select_related('user').all()
        
        if not admins.exists() and options['create']:
            self.stdout.write(self.style.WARNING('No admins found. Creating a default admin...'))
            self._create_default_admin()
            admins = Admin.objects.select_related('user').all()
        
        if not admins.exists():
            self.stdout.write(
                self.style.ERROR(
                    '\n❌ No admin users found!\n\n'
                    'To create an admin user, run:\n'
                    '  python manage.py createsuperuser\n\n'
                    'Or use this command with --create flag:\n'
                    '  python manage.py list_admins --create\n'
                )
            )
            return
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('ADMIN USERS'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
        
        for idx, admin in enumerate(admins, 1):
            user = admin.user
            roles = admin.roles.all()
            role_names = ', '.join([role.name for role in roles]) if roles.exists() else 'No roles'
            
            self.stdout.write(f'{idx}. Username: {self.style.SUCCESS(user.username)}')
            self.stdout.write(f'   Email: {user.email or "Not set"}')
            self.stdout.write(f'   Admin Code: {admin.admin_code}')
            self.stdout.write(f'   Roles: {role_names}')
            self.stdout.write(f'   Is Staff: {self.style.SUCCESS("Yes" if user.is_staff else "No")}')
            self.stdout.write(f'   Is Superuser: {self.style.SUCCESS("Yes" if user.is_superuser else "No")}')
            self.stdout.write(f'   Is Active: {self.style.SUCCESS("Yes" if user.is_active else "No")}')
            
            # Show password hint (can't show actual password)
            if user.has_usable_password():
                self.stdout.write(f'   Password: {self.style.WARNING("*** (set) - Cannot display actual password")}')
            else:
                self.stdout.write(f'   Password: {self.style.ERROR("Not set")}')
            
            self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(
            self.style.WARNING(
                '\n⚠️  Note: Passwords are encrypted and cannot be displayed.\n'
                '   If you forgot the password, reset it using:\n'
                '   python manage.py changepassword <username>\n'
            )
        )
    
    def _create_default_admin(self):
        """Create a default admin user."""
        username = 'admin'
        email = 'admin@shwariphones.com'
        password = 'admin123'
        admin_code = 'ADMIN001'
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(f'User "{username}" already exists. Skipping creation.'))
            return
        
        try:
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_staff=True,
                is_superuser=True
            )
            
            # Create admin profile
            admin = Admin.objects.create(
                user=user,
                admin_code=admin_code
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✅ Created default admin user!\n'
                    f'   Username: {username}\n'
                    f'   Password: {password}\n'
                    f'   Admin Code: {admin_code}\n'
                )
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create admin: {e}')
            )






