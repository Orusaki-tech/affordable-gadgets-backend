"""Management command to create default brand from environment variables (for deployment)."""
import os
import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.models import Brand


class Command(BaseCommand):
    help = 'Create default brand from environment variables (for deployment)'
    # Skip system checks to avoid CORS warnings during deployment
    requires_system_checks = []
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-checks',
            action='store_true',
            help='Skip system checks (useful during deployment)',
        )

    def handle(self, *args, **options):
        try:
            # Get brand details from environment variables with defaults
            brand_code = os.environ.get('NEXT_PUBLIC_BRAND_CODE', 'AFFORDABLE_GADGETS')
            brand_name = os.environ.get('NEXT_PUBLIC_BRAND_NAME', 'Affordable Gadgets')
            brand_description = os.environ.get('BRAND_DESCRIPTION', 'Quality electronics at great prices. Shop phones, laptops, tablets, and accessories with confidence.')
            
            self.stdout.write(f'Attempting to create brand: {brand_code} ({brand_name})')
            
            # Check if brand already exists
            try:
                with transaction.atomic():
                    brand, created = Brand.objects.get_or_create(
                        code=brand_code,
                        defaults={
                            'name': brand_name,
                            'description': brand_description,
                            'is_active': True,
                        }
                    )
            except Exception as db_error:
                self.stdout.write(
                    self.style.WARNING(f'Database error during brand creation: {db_error}')
                )
                # Try to check if brand exists without transaction
                try:
                    brand = Brand.objects.get(code=brand_code)
                    created = False
                except Brand.DoesNotExist:
                    # If we can't create it, that's okay - it might already exist from a previous run
                    self.stdout.write(
                        self.style.WARNING(f'Could not create brand {brand_code}. It may already exist or there may be a database issue.')
                    )
                    return
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Unexpected error checking for brand: {e}')
                    )
                    return
                
                if created:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\n✅ Created default brand successfully!\n'
                            f'   Code: {brand_code}\n'
                            f'   Name: {brand_name}\n'
                            f'   Active: True\n'
                        )
                    )
                else:
                    # Ensure brand is active
                    if not brand.is_active:
                        brand.is_active = True
                        brand.save()
                        self.stdout.write(
                            self.style.SUCCESS(f'Activated existing brand "{brand_code}"')
                        )
                    else:
                        self.stdout.write(
                            self.style.SUCCESS(f'Brand "{brand_code}" already exists and is active. Skipping creation.')
                        )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Failed to create default brand: {e}')
            )
            # Print full traceback for debugging
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            # Don't exit with error code - allow deployment to continue
            # The build script will catch this and continue
            return
