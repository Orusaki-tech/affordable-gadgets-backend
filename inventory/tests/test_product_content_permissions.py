from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Admin, AdminRole, Product


class ProductContentPermissionTests(APITestCase):
    def setUp(self):
        User = get_user_model()

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

        self.creator_user = User.objects.create_user(
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

        self.sales_user = User.objects.create_user(
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

        self.product = Product.objects.create(product_name="Test Product")

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
