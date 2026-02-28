"""Management command to promote an existing user to superuser (and staff)."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()


class Command(BaseCommand):
    help = "Promote an existing user to superuser (and staff) by username or email."

    def add_arguments(self, parser):
        parser.add_argument(
            "username_or_email",
            type=str,
            help="Username or email of the user to promote to superuser.",
        )

    def handle(self, *args, **options):
        identifier = options["username_or_email"].strip()
        if not identifier:
            self.stdout.write(self.style.ERROR("Please provide a username or email."))
            return

        user = None
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR(f'No user found with email "{identifier}".')
                )
                return
        else:
            user = User.objects.filter(username__iexact=identifier).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR(f'No user found with username "{identifier}".')
                )
                return

        if user.is_superuser and user.is_staff:
            self.stdout.write(
                self.style.WARNING(
                    f'User "{user.username}" (id={user.id}) is already a superuser and staff.'
                )
            )
            return

        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(
            self.style.SUCCESS(
                f'Promoted "{user.username}" (email={user.email}, id={user.id}) to superuser and staff.'
            )
        )
        self.stdout.write(
            "They can log in again; the admin UI will show Superuser and full access."
        )
