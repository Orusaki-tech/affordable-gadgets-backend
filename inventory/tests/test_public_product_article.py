from django.db import IntegrityError
from django.urls import reverse
from django.utils.text import slugify
from rest_framework import status
from rest_framework.test import APITestCase

from inventory.models import Product, ProductArticle


class PublicProductArticleApiTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(
            product_name="Article API Product",
            brand="TestBrand",
            model_series="TestModel",
            product_type=Product.ProductType.PHONE,
            slug="article-api-product",
            is_published=True,
        )
        self.article = ProductArticle.objects.create(
            product=self.product,
            slug="test-headline",
            headline="Test headline",
            seo_title="Test SEO title",
            seo_description="Test meta description for the article page.",
            body="# Hello\n\nThis is **markdown**.",
            is_published=True,
            is_primary=True,
        )

    def test_published_article_returns_json(self):
        url = reverse(
            "public-product-article-by-product-slug",
            kwargs={"product_slug": "article-api-product"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["headline"], "Test headline")
        self.assertEqual(response.data["slug"], "test-headline")
        self.assertIn("markdown", response.data["body"])

    def test_article_detail_by_slugs(self):
        url = reverse(
            "public-product-article-detail-by-slugs",
            kwargs={"product_slug": "article-api-product", "article_slug": "test-headline"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "test-headline")

    def test_articles_list_for_product(self):
        ProductArticle.objects.create(
            product=self.product,
            slug="second-guide",
            headline="Second guide",
            body="More content",
            is_published=True,
        )
        url = reverse(
            "public-product-articles-by-product-slug",
            kwargs={"product_slug": "article-api-product"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)

    def test_unpublished_returns_404(self):
        self.article.is_published = False
        self.article.save(update_fields=["is_published"])
        url = reverse(
            "public-product-article-by-product-slug",
            kwargs={"product_slug": "article-api-product"},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class PublicArticleListApiTests(APITestCase):
    def setUp(self):
        self.product = Product.objects.create(
            product_name="Carousel Product",
            brand="CarouselBrand",
            model_series="M1",
            product_type=Product.ProductType.PHONE,
            slug="carousel-product",
            is_published=True,
        )
        ProductArticle.objects.create(
            product=self.product,
            slug=slugify("Carousel headline"),
            headline="Carousel headline",
            body="body",
            category=ProductArticle.ArticleCategory.HISTORY_GUIDE,
            is_published=True,
            is_primary=True,
        )

    def test_public_articles_list(self):
        url = reverse("public-article-list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results") or response.data
        self.assertTrue(any(row["headline"] == "Carousel headline" for row in results))

    def test_slug_uniqueness_per_product(self):
        ProductArticle.objects.create(
            product=self.product,
            slug="unique-slug",
            headline="Another",
            body="x",
            is_published=False,
        )
        with self.assertRaises(IntegrityError):
            ProductArticle.objects.create(
                product=self.product,
                slug="unique-slug",
                headline="Duplicate slug",
                body="y",
            )


class PublicProductListHasPublishedArticleTests(APITestCase):
    """Public product list exposes has_published_article from queryset annotation."""

    def setUp(self):
        brand = "HasArticleListBrandXYZ"
        self.published_guide = Product.objects.create(
            product_name="Product With Published Guide",
            brand=brand,
            model_series="M1",
            product_type=Product.ProductType.PHONE,
            slug="list-test-with-published-guide",
            is_published=True,
        )
        ProductArticle.objects.create(
            product=self.published_guide,
            slug="published-guide",
            headline="H",
            seo_title="1234567890",
            seo_description="x" * 20,
            body="body",
            is_published=True,
            is_primary=True,
        )
        self.draft_only = Product.objects.create(
            product_name="Product Draft Article Only",
            brand=brand,
            model_series="M2",
            product_type=Product.ProductType.PHONE,
            slug="list-test-draft-article-only",
            is_published=True,
        )
        ProductArticle.objects.create(
            product=self.draft_only,
            slug="draft-guide",
            headline="Draft",
            body="secret",
            is_published=False,
        )
        self.no_article = Product.objects.create(
            product_name="Product No Article Row",
            brand=brand,
            model_series="M3",
            product_type=Product.ProductType.PHONE,
            slug="list-test-no-article-row",
            is_published=True,
        )

    def test_has_published_article_matches_annotation(self):
        url = reverse("public-product-list")
        response = self.client.get(url, {"search": "HasArticleListBrandXYZ", "page_size": 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results") or []
        by_slug = {row["slug"]: row.get("has_published_article") for row in results}
        self.assertTrue(by_slug.get("list-test-with-published-guide"))
        self.assertFalse(by_slug.get("list-test-draft-article-only"))
        self.assertFalse(by_slug.get("list-test-no-article-row"))
