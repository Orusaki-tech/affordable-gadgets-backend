from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Admin, AdminRole, Product, ProductArticle


class ProductContentPermissionTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()

        self.content_role, _ = AdminRole.objects.get_or_create(
            name=AdminRole.RoleChoices.CONTENT_CREATOR,
            defaults={
                "display_name": "Content Creator",
                "description": "Can create reviews and content",
            },
        )
        self.sales_role, _ = AdminRole.objects.get_or_create(
            name=AdminRole.RoleChoices.SALESPERSON,
            defaults={
                "display_name": "Salesperson",
                "description": "Can view inventory and create orders",
            },
        )

        self.creator_user = user_model.objects.create_user(
            username="content_creator",
            email="content@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.creator_admin = Admin.objects.create(
            user=self.creator_user,
            admin_code="ADM-CC-001",
        )
        self.creator_admin.roles.add(self.content_role)

        self.sales_user = user_model.objects.create_user(
            username="salesperson",
            email="sales@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.sales_admin = Admin.objects.create(
            user=self.sales_user,
            admin_code="ADM-SP-001",
        )
        self.sales_admin.roles.add(self.sales_role)

        self.im_role, _ = AdminRole.objects.get_or_create(
            name=AdminRole.RoleChoices.INVENTORY_MANAGER,
            defaults={
                "display_name": "Inventory Manager",
                "description": "Manages inventory",
            },
        )
        self.im_user = user_model.objects.create_user(
            username="inventory_manager",
            email="im@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.im_admin = Admin.objects.create(
            user=self.im_user,
            admin_code="ADM-IM-001",
        )
        self.im_admin.roles.add(self.im_role)

        self.product = Product.objects.create(
            product_name="Test Product",
            brand="TestBrand",
            model_series="TestModel",
            product_type=Product.ProductType.PHONE,
        )

    def test_content_creator_can_update_content(self):
        self.client.force_authenticate(user=self.creator_user)

        url = reverse("product-update-content", args=[self.product.id])
        response = self.client.patch(
            url,
            {"product_description": "Updated description"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.product_description, "Updated description")

    def test_salesperson_cannot_update_content(self):
        self.client.force_authenticate(user=self.sales_user)

        url = reverse("product-update-content", args=[self.product.id])
        response = self.client.patch(
            url,
            {"product_description": "Should be denied"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_salesperson_cannot_update_content_article(self):
        self.client.force_authenticate(user=self.sales_user)
        url = reverse("product-update-content", args=[self.product.id])
        response = self.client.patch(
            url,
            {
                "article": {
                    "headline": "Should fail",
                    "body": "x",
                    "seo_title": "1234567890",
                    "seo_description": "y" * 20,
                    "is_published": True,
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_inventory_manager_can_update_content(self):
        self.client.force_authenticate(user=self.im_user)

        url = reverse("product-update-content", args=[self.product.id])
        response = self.client.patch(
            url,
            {"product_description": "IM updated description"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.product.refresh_from_db()
        self.assertEqual(self.product.product_description, "IM updated description")

    def test_content_creator_can_upsert_article_via_update_content(self):
        self.client.force_authenticate(user=self.creator_user)
        url = reverse("product-update-content", args=[self.product.id])
        payload = {
            "article": {
                "headline": "Buying guide headline",
                "body": "# Section\n\nBody text.",
                "seo_title": "1234567890",
                "seo_description": "d" * 20,
                "is_published": True,
            }
        }
        response = self.client.patch(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        art = ProductArticle.objects.get(product=self.product)
        self.assertEqual(art.headline, "Buying guide headline")
        self.assertTrue(art.is_published)

        response2 = self.client.patch(
            url,
            {"article": {"headline": "Updated headline", "is_published": False}},
            format="json",
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        art.refresh_from_db()
        self.assertEqual(art.headline, "Updated headline")
        self.assertFalse(art.is_published)

    def test_inventory_manager_can_patch_article_via_partial_update(self):
        self.client.force_authenticate(user=self.im_user)
        url = reverse("product-detail", args=[self.product.id])
        response = self.client.patch(
            url,
            {
                "article": {
                    "headline": "IM wrote this",
                    "body": "Markdown here",
                    "seo_title": "abcdefghij",
                    "seo_description": "e" * 22,
                    "is_published": True,
                }
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        art = ProductArticle.objects.get(product=self.product)
        self.assertEqual(art.headline, "IM wrote this")
        self.assertTrue(art.is_published)

    def test_content_creator_cannot_partial_update_article(self):
        self.client.force_authenticate(user=self.creator_user)
        url = reverse("product-detail", args=[self.product.id])
        response = self.client.patch(
            url,
            {"article": {"headline": "Should not apply"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_salesperson_cannot_partial_update_article(self):
        self.client.force_authenticate(user=self.sales_user)
        url = reverse("product-detail", args=[self.product.id])
        response = self.client.patch(
            url,
            {"article": {"headline": "Should not apply"}},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
