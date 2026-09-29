from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Product, ProductImage


class PublicProductImagesTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(
            product_name="Multi Image Phone",
            brand="Apple",
            product_type=Product.ProductType.PHONE,
            is_published=True,
            slug="multi-image-phone",
        )
        tiny = SimpleUploadedFile("a.jpg", b"fake-image-bytes", content_type="image/jpeg")
        ProductImage.objects.create(
            product=self.product,
            image=tiny,
            is_primary=False,
            display_order=2,
            alt_text="side",
        )
        tiny2 = SimpleUploadedFile("b.jpg", b"fake-image-bytes-2", content_type="image/jpeg")
        ProductImage.objects.create(
            product=self.product,
            image=tiny2,
            is_primary=True,
            display_order=1,
            alt_text="front",
        )
        tiny3 = SimpleUploadedFile("c.jpg", b"fake-image-bytes-3", content_type="image/jpeg")
        ProductImage.objects.create(
            product=self.product,
            image=tiny3,
            is_primary=False,
            display_order=3,
            alt_text="back",
        )

    def test_retrieve_includes_all_images_primary_first(self):
        response = self.client.get(f"/api/v1/public/products/{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        images = response.data.get("images") or []
        self.assertEqual(len(images), 3)
        self.assertTrue(images[0]["is_primary"])
        self.assertEqual(images[0]["alt_text"], "front")
        self.assertEqual([img["alt_text"] for img in images], ["front", "side", "back"])
        self.assertTrue(response.data.get("primary_image"))

    def test_slug_lookup_includes_all_images(self):
        response = self.client.get("/api/v1/public/products/", {"slug": self.product.slug})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results") or []
        self.assertEqual(len(results), 1)
        images = results[0].get("images") or []
        self.assertEqual(len(images), 3)
        self.assertTrue(images[0]["is_primary"])

    def test_catalog_list_omits_images_array(self):
        response = self.client.get("/api/v1/public/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results") or []
        self.assertTrue(len(results) >= 1)
        match = next((p for p in results if p.get("id") == self.product.id), results[0])
        self.assertNotIn("images", match)
        self.assertIn("primary_image", match)
