from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Admin, AdminRole, Product


class ProductImagePermissionTests(APITestCase):
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
            username="content_creator_images",
            email="content.images@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.creator_admin = Admin.objects.create(
            user=self.creator_user,
            admin_code="ADM-CC-IMG-001",
        )
        self.creator_admin.roles.add(self.content_role)

        self.sales_user = User.objects.create_user(
            username="salesperson_images",
            email="sales.images@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.sales_admin = Admin.objects.create(
            user=self.sales_user,
            admin_code="ADM-SP-IMG-001",
        )
        self.sales_admin.roles.add(self.sales_role)

        self.product = Product.objects.create(product_name="Test Product Images")

        self.image_file = SimpleUploadedFile(
            "test-image.jpg",
            b"\x47\x49\x46\x38\x39\x61",
            content_type="image/jpeg",
        )

    def test_content_creator_can_create_product_image(self):
        self.client.force_authenticate(user=self.creator_user)

        url = reverse("product-image-list")
        with patch(
            "inventory.cloudinary_utils.upload_image_to_cloudinary",
            return_value=("product_photos/test-image.jpg", "https://example.com/test.jpg"),
        ):
            response = self.client.post(
                url,
                {"product": self.product.id, "image": self.image_file},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_salesperson_cannot_create_product_image(self):
        self.client.force_authenticate(user=self.sales_user)

        url = reverse("product-image-list")
        response = self.client.post(
            url,
            {"product": self.product.id, "image": self.image_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
