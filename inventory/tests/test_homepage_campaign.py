from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Admin, AdminRole, HomepageCampaign, HomepageCampaignProduct, Product


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
