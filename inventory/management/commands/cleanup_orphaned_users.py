"""Management command to find and optionally delete orphaned User accounts."""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from inventory.models import Admin, Customer
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Find and optionally delete User accounts that have no Admin or Customer profile'

    def add_arguments(self, parser):
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Actually delete the orphaned users (default is dry-run)',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Check and delete a specific email address if orphaned',
        )

    def handle(self, *args, **options):
        delete = options.get('delete', False)
        email_filter = options.get('email', None)
        
        self.stdout.write(self.style.WARNING('\n' + '='*60))
        self.stdout.write(self.style.WARNING('Find Orphaned User Accounts'))
        self.stdout.write(self.style.WARNING('='*60 + '\n'))
        
        # Get all users
        if email_filter:
            users = User.objects.filter(email=email_filter)
            self.stdout.write(f'Checking specific email: {email_filter}\n')
        else:
            users = User.objects.all()
        
        orphaned_users = []
        
        for user in users:
            has_admin = Admin.objects.filter(user=user).exists()
            has_customer = Customer.objects.filter(user=user).exists()
            
            # A user is orphaned if they have neither Admin nor Customer profile
            # AND they're not a superuser (we don't want to delete superusers)
            if not has_admin and not has_customer and not user.is_superuser:
                orphaned_users.append(user)
        
        if not orphaned_users:
            self.stdout.write(self.style.SUCCESS('✅ No orphaned users found.'))
            if email_filter:
                self.stdout.write(f'   Email {email_filter} is either in use or belongs to a superuser.')
            return
        
        self.stdout.write(self.style.ERROR(f'Found {len(orphaned_users)} orphaned user(s):\n'))
        
        for user in orphaned_users:
            self.stdout.write(f'  ✗ User ID {user.id}: {user.username} ({user.email})')
            self.stdout.write(f'    Is Staff: {user.is_staff}, Is Superuser: {user.is_superuser}')
        
        if not delete:
            self.stdout.write('\n' + self.style.WARNING('🔍 DRY RUN MODE - No changes will be made.'))
            self.stdout.write(self.style.WARNING('   Run with --delete to actually delete these users.'))
            if email_filter:
                self.stdout.write(f'\n   To delete the user with email {email_filter}, run:')
                self.stdout.write(f'   python manage.py cleanup_orphaned_users --email {email_filter} --delete')
            return
        
        # Confirm deletion
        self.stdout.write('\n' + '='*60)
        response = input(f'\n⚠️  Are you sure you want to delete {len(orphaned_users)} orphaned user(s)? (yes/no): ')
        
        if response.lower() not in ['yes', 'y']:
            self.stdout.write(self.style.ERROR('❌ Deletion cancelled.'))
            return
        
        # Delete orphaned users
        deleted_count = 0
        try:
            with transaction.atomic():
                for user in orphaned_users:
                    username = user.username
                    email = user.email
                    user.delete()
                    deleted_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Deleted orphaned user: {username} ({email})')
                    )
            
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS(f'✅ Successfully deleted {deleted_count} orphaned user(s)'))
            self.stdout.write('='*60 + '\n')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error during deletion: {str(e)}'))
            import traceback
            self.stdout.write(traceback.format_exc())
            raise





