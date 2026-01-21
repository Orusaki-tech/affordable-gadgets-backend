from django.core.management.base import BaseCommand
from django.contrib.auth import authenticate, get_user_model
from inventory.models import Admin
from rest_framework.authtoken.models import Token
from inventory.serializers import AdminAuthTokenSerializer

User = get_user_model()

class Command(BaseCommand):
    help = 'Test Fabian\'s login credentials and status'

    def handle(self, *args, **options):
        email = "fabian@shwariphones.com"
        password = "00000000"
        
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS("TESTING FABIAN'S LOGIN"))
        self.stdout.write("="*70)
        
        # Check if user exists
        try:
            user = User.objects.get(email__iexact=email)
            self.stdout.write(f"\n✅ User found:")
            self.stdout.write(f"   Username: {user.username}")
            self.stdout.write(f"   Email: {user.email}")
            self.stdout.write(f"   ID: {user.id}")
            self.stdout.write(f"   is_active: {user.is_active}")
            self.stdout.write(f"   is_staff: {user.is_staff}")
            self.stdout.write(f"   is_superuser: {user.is_superuser}")
            
            # Check admin profile
            try:
                admin = Admin.objects.get(user=user)
                self.stdout.write(f"   Admin Profile: EXISTS (admin_code: {admin.admin_code})")
            except Admin.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"   Admin Profile: MISSING"))
            
            # Test Django authentication
            self.stdout.write(f"\n{'='*70}")
            self.stdout.write("TESTING DJANGO AUTHENTICATION")
            self.stdout.write("="*70)
            authenticated_user = authenticate(username=user.username, password=password)
            if authenticated_user:
                self.stdout.write(self.style.SUCCESS(f"✅ Django authentication SUCCESS"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Django authentication FAILED - Invalid password"))
                return
            
            # Test serializer with email
            self.stdout.write(f"\n{'='*70}")
            self.stdout.write("TESTING AdminAuthTokenSerializer (with email)")
            self.stdout.write("="*70)
            
            serializer_email = AdminAuthTokenSerializer(data={
                'username': email,
                'password': password
            })
            
            if serializer_email.is_valid():
                self.stdout.write(self.style.SUCCESS(f"✅ Serializer validation SUCCESS (with email)"))
                validated_user = serializer_email.validated_data['user']
                self.stdout.write(f"   Authenticated user: {validated_user.username}")
                self.stdout.write(f"   is_staff: {validated_user.is_staff}")
                self.stdout.write(f"   is_superuser: {validated_user.is_superuser}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ Serializer validation FAILED (with email)"))
                self.stdout.write(f"   Errors: {serializer_email.errors}")
                return
            
            # Test serializer with username
            serializer_username = AdminAuthTokenSerializer(data={
                'username': user.username,
                'password': password
            })
            
            if serializer_username.is_valid():
                self.stdout.write(self.style.SUCCESS(f"✅ Serializer validation SUCCESS (with username)"))
            else:
                self.stdout.write(self.style.ERROR(f"❌ Serializer validation FAILED (with username)"))
                self.stdout.write(f"   Errors: {serializer_username.errors}")
            
            # Check token
            self.stdout.write(f"\n{'='*70}")
            self.stdout.write("CHECKING AUTH TOKEN")
            self.stdout.write("="*70)
            try:
                token = Token.objects.get(user=user)
                self.stdout.write(self.style.SUCCESS(f"✅ Token exists: {token.key[:20]}..."))
            except Token.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"⚠️  Token does not exist (will be created on login)"))
            
            # Final status
            self.stdout.write(f"\n{'='*70}")
            self.stdout.write("FINAL STATUS")
            self.stdout.write("="*70)
            if user.is_staff or user.is_superuser:
                self.stdout.write(self.style.SUCCESS(f"✅ User CAN login via AdminTokenLoginView"))
                self.stdout.write(f"   Reason: User has is_staff={user.is_staff} or is_superuser={user.is_superuser}")
            else:
                self.stdout.write(self.style.ERROR(f"❌ User CANNOT login via AdminTokenLoginView"))
                self.stdout.write(f"   Reason: User does not have is_staff=True")
                self.stdout.write(f"\n   FIX: Setting is_staff=True for this user...")
                user.is_staff = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f"   ✅ Fixed! User can now login."))
            
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"\n❌ User not found with email: {email}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Error: {str(e)}"))
            import traceback
            traceback.print_exc()
