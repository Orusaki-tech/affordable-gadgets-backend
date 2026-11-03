from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.homepage_campaign import seasonal_unit_price
from inventory.models import (
    Admin,
    AdminRole,
    HomepageCampaign,
    HomepageCampaignProduct,
    InventoryUnit,
    Product,
)


class HomepageCampaignApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.content_role, _ = AdminRole.objects.get_or_create(
            name=AdminRole.RoleChoices.CONTENT_CREATOR,
            defaults={
                "display_name": "Content Creator",
                "description": "Can edit storefront content",
            },
        )
        self.sales_role, _ = AdminRole.objects.get_or_create(
            name=AdminRole.RoleChoices.SALESPERSON,
            defaults={
                "display_name": "Salesperson",
                "description": "Read-only studio",
            },
        )
        self.creator = user_model.objects.create_user(
            username="campaign_creator",
            email="campaign.creator@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        creator_admin = Admin.objects.create(user=self.creator, admin_code="ADM-CC-CAMP-001")
        creator_admin.roles.add(self.content_role)

        self.salesperson = user_model.objects.create_user(
            username="campaign_sales",
            email="campaign.sales@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        sales_admin = Admin.objects.create(user=self.salesperson, admin_code="ADM-SP-CAMP-001")
        sales_admin.roles.add(self.sales_role)

        self.first = Product.objects.create(
            product_name="Campaign Phone A",
            brand="TestBrand",
            model_series="A",
            product_type=Product.ProductType.PHONE,
            slug="campaign-phone-a",
            is_published=True,
        )
        self.second = Product.objects.create(
            product_name="Campaign Phone B",
            brand="TestBrand",
            model_series="B",
            product_type=Product.ProductType.PHONE,
            slug="campaign-phone-b",
            is_published=True,
        )
        self.public_url = reverse("public-homepage-campaign")
        self.staff_url = reverse("homepage-campaign")

    def test_public_preserves_order_and_hides_when_inactive_or_out_of_window(self):
        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            self.staff_url,
            {
                "title": "Black November",
                "animation": "title_shimmer",
                "is_active": True,
                "product_ids": [self.second.id, self.first.id],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["id"] for item in response.data["products"]],
            [self.second.id, self.first.id],
        )

        self.client.force_authenticate(user=None)
        public = self.client.get(self.public_url)
        self.assertEqual(public.status_code, status.HTTP_200_OK)
        self.assertEqual(public.data["title"], "Black November")
        self.assertEqual(public.data["animation"], "title_shimmer")
        self.assertEqual(
            [item["id"] for item in public.data["products"]],
            [self.second.id, self.first.id],
        )

        campaign = HomepageCampaign.objects.get(key="seasonal")
        campaign.is_active = False
        campaign.save(update_fields=["is_active"])
        hidden = self.client.get(self.public_url)
        self.assertEqual(hidden.data["products"], [])
        self.assertEqual(hidden.data["title"], "Black November")

        campaign.is_active = True
        campaign.starts_at = timezone.now() + timedelta(days=2)
        campaign.ends_at = timezone.now() + timedelta(days=10)
        campaign.save(update_fields=["is_active", "starts_at", "ends_at"])
        upcoming = self.client.get(self.public_url)
        self.assertEqual(upcoming.data["products"], [])

        positions = list(
            HomepageCampaignProduct.objects.filter(campaign=campaign)
            .order_by("position")
            .values_list("product_id", flat=True)
        )
        self.assertEqual(positions, [self.second.id, self.first.id])

    def test_promo_price_and_image_are_returned_on_the_card(self):
        image = BytesIO()
        Image.new("RGB", (8, 8), color="black").save(image, "JPEG")
        upload = SimpleUploadedFile("promo.jpg", image.getvalue(), content_type="image/jpeg")
        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            self.staff_url,
            {
                "title": "Black November",
                "products": '[{"product_id": %d, "promo_price": "39999.00"}]' % self.first.id,
                "promo_image_%d" % self.first.id: upload,
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        saved = response.data["products"][0]
        self.assertEqual(saved["id"], self.first.id)
        self.assertEqual(Decimal(str(saved["promo_price"])), Decimal("39999.00"))
        self.assertIn("/campaigns/", saved["promo_image_url"])
        self.assertTrue(saved["promo_image_url"].endswith(".jpg"))

        self.client.force_authenticate(user=None)
        public = self.client.get(self.public_url)
        card = public.data["products"][0]
        self.assertEqual(card["promo_price"], 39999.0)
        self.assertIn("/campaigns/", card["promo_image_url"])
        self.assertNotEqual(card["primary_image"], card["promo_image_url"])

    def test_unpublished_chosen_product_still_appears(self):
        self.second.is_published = False
        self.second.save(update_fields=["is_published"])
        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            self.staff_url,
            {"product_ids": [self.first.id, self.second.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.force_authenticate(user=None)
        public = self.client.get(self.public_url)
        self.assertEqual(
            [item["id"] for item in public.data["products"]],
            [self.first.id, self.second.id],
        )

    def test_campaign_price_is_the_checkout_price(self):
        InventoryUnit.objects.create(
            product_template=self.first,
            selling_price=Decimal("21500.00"),
            cost_of_unit=Decimal("10000.00"),
            serial_number="CAMP-A-128",
        )
        higher = InventoryUnit.objects.create(
            product_template=self.first,
            selling_price=Decimal("25000.00"),
            cost_of_unit=Decimal("12000.00"),
            serial_number="CAMP-A-256",
        )
        self.client.force_authenticate(user=self.creator)
        response = self.client.patch(
            self.staff_url,
            {"products": [{"product_id": self.first.id, "promo_price": "19500.00"}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(seasonal_unit_price(self.first, Decimal("21500.00")), Decimal("19500.00"))
        self.assertEqual(seasonal_unit_price(self.first, higher.selling_price), Decimal("22674.42"))

        campaign = HomepageCampaign.objects.get(key="seasonal")
        campaign.is_active = False
        campaign.save(update_fields=["is_active"])
        self.assertIsNone(seasonal_unit_price(self.first, Decimal("21500.00")))

    def test_salesperson_cannot_update(self):
        self.client.force_authenticate(user=self.salesperson)
        response = self.client.patch(
            self.staff_url,
            {"title": "Should fail", "product_ids": [self.first.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        campaign = HomepageCampaign.objects.get(key="seasonal")
        self.assertNotEqual(campaign.title, "Should fail")
