from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Admin, AdminRole, Product, ProductImage


class InventoryManagerProductImageUploadTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()

        self.inventory_role, _ = AdminRole.objects.get_or_create(
            name=AdminRole.RoleChoices.INVENTORY_MANAGER,
            defaults={
                "display_name": "Inventory Manager",
                "description": "Can manage products and inventory",
            },
        )
        self.sales_role, _ = AdminRole.objects.get_or_create(
            name=AdminRole.RoleChoices.SALESPERSON,
            defaults={
                "display_name": "Salesperson",
                "description": "Can view inventory and create orders",
            },
        )

        self.im_user = user_model.objects.create_user(
            username="inventory_manager_images",
            email="im.images@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.im_admin = Admin.objects.create(user=self.im_user, admin_code="ADM-IM-IMG-001")
        self.im_admin.roles.add(self.inventory_role)

        self.sales_user = user_model.objects.create_user(
            username="salesperson_images_upload",
            email="sales.upload@example.com",
            password="test-pass-123",
            is_staff=True,
        )
        self.sales_admin = Admin.objects.create(user=self.sales_user, admin_code="ADM-SP-IMG-002")
        self.sales_admin.roles.add(self.sales_role)

        self.product = Product.objects.create(product_name="Upload Images Product")

        self.image_file_1 = SimpleUploadedFile(
            "test-image-1.jpg",
            b"\x47\x49\x46\x38\x39\x61",
            content_type="image/jpeg",
        )
        self.image_file_2 = SimpleUploadedFile(
            "test-image-2.jpg",
            b"\x47\x49\x46\x38\x39\x61",
            content_type="image/jpeg",
        )

    def test_inventory_manager_can_upload_multiple_images_from_product_endpoint(self):
        self.client.force_authenticate(user=self.im_user)
        url = reverse("product-upload-images", args=[self.product.id])

        with patch(
            "inventory.cloudinary_utils.upload_image_to_cloudinary",
            side_effect=[
                ("product_photos/test-image-1.jpg", "https://example.com/1.jpg"),
                ("product_photos/test-image-2.jpg", "https://example.com/2.jpg"),
            ],
        ):
            response = self.client.post(
                url,
                {
                    "images": [self.image_file_1, self.image_file_2],
                    "alt_text": "Alt text",
                    "make_primary": "true",
                    "start_display_order": "10",
                },
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ProductImage.objects.filter(product=self.product).count(), 2)
        primary = ProductImage.objects.filter(product=self.product, is_primary=True).first()
        self.assertIsNotNone(primary)

        images = list(ProductImage.objects.filter(product=self.product).order_by("display_order", "id"))
        self.assertEqual(images[0].display_order, 10)
        self.assertEqual(images[1].display_order, 11)

    def test_salesperson_cannot_upload_images_from_product_endpoint(self):
        self.client.force_authenticate(user=self.sales_user)
        url = reverse("product-upload-images", args=[self.product.id])

        response = self.client.post(
            url,
            {"images": [self.image_file_1]},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

