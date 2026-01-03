"""Management command to check if an email is in use and by what."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from inventory.models import Admin, Customer

User = get_user_model()


class Command(BaseCommand):
    help = 'Check if an email address is in use and by what type of account'

    def add_arguments(self, parser):
        parser.add_argument(
            'email',
            type=str,
            help='Email address to check',
        )

    def handle(self, *args, **options):
        email = options['email']
        
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING(f'Checking email: {email}'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        # Check if User exists with this email
        users = User.objects.filter(email=email)
        
        if not users.exists():
            self.stdout.write(self.style.SUCCESS(f'✅ Email {email} is NOT in use. Available for new accounts.'))
            return
        
        self.stdout.write(self.style.ERROR(f'❌ Email {email} is in use by {users.count()} user(s):\n'))
        
        for user in users:
            self.stdout.write(f'User ID: {user.id}')
            self.stdout.write(f'Username: {user.username}')
            self.stdout.write(f'Email: {user.email}')
            self.stdout.write(f'Is Staff: {user.is_staff}')
            self.stdout.write(f'Is Superuser: {user.is_superuser}')
            self.stdout.write(f'Is Active: {user.is_active}')
            self.stdout.write(f'Date Joined: {user.date_joined}')
            
            # Check if user has Admin profile
            try:
                admin = Admin.objects.get(user=user)
                self.stdout.write(self.style.ERROR(f'  → Has Admin Profile: {admin.admin_code}'))
            except Admin.DoesNotExist:
                self.stdout.write(self.style.SUCCESS('  → No Admin Profile'))
            
            # Check if user has Customer profile
            try:
                customer = Customer.objects.get(user=user)
                self.stdout.write(self.style.WARNING(f'  → Has Customer Profile: ID {customer.id}'))
            except Customer.DoesNotExist:
                self.stdout.write(self.style.SUCCESS('  → No Customer Profile'))
            
            self.stdout.write('')
        
        self.stdout.write('='*60 + '\n')





