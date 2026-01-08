"""Management command to create default brand from environment variables (for deployment)."""
import os
from django.core.management.base import BaseCommand
from inventory.models import Brand


class Command(BaseCommand):
    help = 'Create default brand from environment variables (for deployment)'

    def handle(self, *args, **options):
        # Get brand details from environment variables with defaults
        brand_code = os.environ.get('NEXT_PUBLIC_BRAND_CODE', 'AFFORDABLE_GADGETS')
        brand_name = os.environ.get('NEXT_PUBLIC_BRAND_NAME', 'Affordable Gadgets')
        brand_description = os.environ.get('BRAND_DESCRIPTION', 'Quality electronics at great prices. Shop phones, laptops, tablets, and accessories with confidence.')
        
        # Check if brand already exists
        brand, created = Brand.objects.get_or_create(
            code=brand_code,
            defaults={
                'name': brand_name,
                'description': brand_description,
                'is_active': True,
            }
        )
        
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
