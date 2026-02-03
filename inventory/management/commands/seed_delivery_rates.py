import csv
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from inventory.models import DeliveryRate


COUNTIES = [
    "Baringo", "Bomet", "Bungoma", "Busia", "Elgeyo-Marakwet", "Embu", "Garissa",
    "Homa Bay", "Isiolo", "Kajiado", "Kakamega", "Kericho", "Kiambu", "Kilifi",
    "Kirinyaga", "Kisii", "Kisumu", "Kitui", "Kwale", "Laikipia", "Lamu",
    "Machakos", "Makueni", "Mandera", "Marsabit", "Meru", "Migori", "Mombasa",
    "Murang'a", "Nairobi", "Nakuru", "Nandi", "Narok", "Nyamira", "Nyandarua",
    "Nyeri", "Samburu", "Siaya", "Taita-Taveta", "Tana River", "Tharaka-Nithi",
    "Trans Nzoia", "Turkana", "Uasin Gishu", "Vihiga", "Wajir", "West Pokot"
]


class Command(BaseCommand):
    help = "Seed delivery rates for all 47 counties and optional Nairobi/Kiambu wards."

    def add_arguments(self, parser):
        parser.add_argument(
            "--county-price",
            type=Decimal,
            default=Decimal("0.00"),
            help="Default delivery price for county-level rates."
        )
        parser.add_argument(
            "--ward-price",
            type=Decimal,
            default=Decimal("0.00"),
            help="Default delivery price for ward-level rates."
        )
        parser.add_argument(
            "--wards-file",
            type=str,
            default=str(Path(settings.BASE_DIR) / "inventory" / "data" / "wards_nairobi_kiambu.csv"),
            help="CSV file with ward rows: county,ward."
        )
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Update existing rates with provided prices."
        )

    def handle(self, *args, **options):
        county_price = options["county_price"]
        ward_price = options["ward_price"]
        wards_file = Path(options["wards_file"])
        update_existing = options["update_existing"]

        created_counties = 0
        updated_counties = 0
        for county in COUNTIES:
            rate, created = DeliveryRate.objects.get_or_create(
                county=county,
                ward=None,
                defaults={"price": county_price, "is_active": True}
            )
            if created:
                created_counties += 1
            elif update_existing:
                rate.price = county_price
                rate.is_active = True
                rate.save(update_fields=["price", "is_active"])
                updated_counties += 1

        self.stdout.write(self.style.SUCCESS(
            f"County rates seeded. Created: {created_counties}, Updated: {updated_counties}"
        ))

        if not wards_file.exists():
            self.stdout.write(self.style.WARNING(
                f"Wards file not found at {wards_file}. Skipping ward seeding."
            ))
            return

        created_wards = 0
        updated_wards = 0
        with wards_file.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                county = (row.get("county") or "").strip()
                ward = (row.get("ward") or "").strip()
                if not county or not ward:
                    continue
                rate, created = DeliveryRate.objects.get_or_create(
                    county=county,
                    ward=ward,
                    defaults={"price": ward_price, "is_active": True}
                )
                if created:
                    created_wards += 1
                elif update_existing:
                    rate.price = ward_price
                    rate.is_active = True
                    rate.save(update_fields=["price", "is_active"])
                    updated_wards += 1

        self.stdout.write(self.style.SUCCESS(
            f"Ward rates seeded. Created: {created_wards}, Updated: {updated_wards}"
        ))
