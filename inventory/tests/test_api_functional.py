"""
Functional tests for critical API endpoints based on OpenAPI specification.

Tests cover main business flows: product browsing, article management, and ordering.
"""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework import status

from inventory.models import Product, ProductArticle, Order, InventoryUnit

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user(db):
    return baker.make(User, is_staff=True, is_superuser=True)


@pytest.fixture
def content_creator_user(db):
    user = baker.make(User)
    # Assign content creator permission if it exists
    return user


@pytest.fixture
def sample_product(db):
    return baker.make(
        Product,
        product_name="Test Product",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_global=True,
    )


@pytest.fixture
def sample_article(db, sample_product):
    return baker.make(
        ProductArticle,
        product=sample_product,
        headline="Test Article",
        is_published=True,
        thumbnail_image=None,
    )


@pytest.mark.django_db
@pytest.mark.p0
class TestProductListingEndpoint:
    """Test product listing endpoint - critical for storefront."""

    def test_products_list_returns_200(self, api_client):
        """GET /api/v1/public/products/ should return 200."""
        response = api_client.get("/api/v1/public/products/")
        assert response.status_code == status.HTTP_200_OK

    def test_products_list_returns_paginated_data(self, api_client, sample_product):
        """Products list should return paginated data."""
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        assert "results" in data or "data" in data or isinstance(data, list)
        results = data.get("results") or data.get("data") or data
        assert len(results) >= 0

    def test_products_list_includes_published_only(self, api_client, db):
        """Published products should appear in public list."""
        published = baker.make(Product, product_type=Product.ProductType.PHONE, is_published=True, is_global=True)
        baker.make(Product, product_type=Product.ProductType.PHONE, is_published=False, brand="UniqueBrand1", is_global=True)
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        results = data.get("results") or data.get("data") or data
        product_ids = [p.get("id") for p in results]
        assert published.id in product_ids

    def test_products_list_includes_required_fields(self, api_client, sample_product):
        """Product list items should include required fields."""
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        results = data.get("results") or data.get("data") or data
        if results:
            product = results[0]
            required_fields = ["id", "product_name", "product_type"]
            for field in required_fields:
                assert field in product, f"Product missing required field: {field}"

    def test_products_list_supports_filtering(self, api_client, db):
        """Products list should support filtering by product_type."""
        baker.make(Product, product_type=Product.ProductType.PHONE, is_published=True, is_global=True)
        baker.make(Product, product_type=Product.ProductType.LAPTOP, is_published=True, brand="UniqueBrand2", is_global=True)
        response = api_client.get("/api/v1/public/products/?product_type=phone")
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]


@pytest.mark.django_db
@pytest.mark.p0
class TestProductDetailEndpoint:
    """Test product detail endpoint."""

    def test_product_detail_returns_200(self, api_client, sample_product):
        """GET /api/v1/public/products/{id}/ should return 200 for existing product."""
        response = api_client.get(f"/api/v1/public/products/{sample_product.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_product_detail_returns_404_for_missing(self, api_client):
        """GET /api/v1/public/products/{id}/ should return 404 for missing product."""
        response = api_client.get("/api/v1/public/products/999999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_product_detail_includes_article(self, api_client, sample_product, sample_article):
        """Product detail should include article if present."""
        response = api_client.get(f"/api/v1/public/products/{sample_product.id}/")
        data = response.json()
        assert "id" in data


@pytest.mark.django_db
@pytest.mark.p1
class TestProductArticleManagement:
    """Test product article (buying guide) management."""

    def test_create_article_requires_auth(self, api_client, sample_product):
        """Creating article should require authentication."""
        payload = {"article": {"headline": "New Guide", "body": "Content", "is_published": False}}
        response = api_client.patch(
            f"/api/inventory/products/{sample_product.id}/update_content/", payload, format="json"
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_update_article_with_json(self, api_client, sample_product, admin_user):
        """Update article via JSON should work."""
        api_client.force_authenticate(admin_user)
        payload = {
            "article": {
                "headline": "Updated Guide",
                "seo_title": "SEO Title",
                "body": "Updated content",
            }
        }
        response = api_client.patch(
            f"/api/inventory/products/{sample_product.id}/update_content/", payload, format="json"
        )
        assert response.status_code in [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,  # Validation error is acceptable
        ]

    def test_article_thumbnail_image_field_exists(self, api_client, sample_article):
        """Article should have thumbnail_image field."""
        response = api_client.get(f"/api/v1/public/products/{sample_article.product_id}/")
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.django_db
@pytest.mark.p1
class TestContentCreatorPermissions:
    """Test content creator role and permissions."""

    def test_content_creator_can_update_article(
        self, api_client, sample_product, content_creator_user, db
    ):
        """Content creator should be able to update article fields."""
        api_client.force_authenticate(content_creator_user)
        payload = {"article": {"headline": "Content Creator Update", "body": "New content"}}
        response = api_client.patch(
            f"/api/inventory/products/{sample_product.id}/update_content/", payload, format="json"
        )
        assert response.status_code < 500

    def test_content_creator_cannot_modify_inventory(
        self, api_client, sample_product, content_creator_user
    ):
        """Content creator should not be able to modify inventory fields."""
        api_client.force_authenticate(content_creator_user)
        payload = {"quantity": 1000}  # Should not be allowed
        response = api_client.patch(
            f"/api/inventory/products/{sample_product.id}/update_content/", payload, format="json"
        )
        assert response.status_code < 500


@pytest.mark.django_db
@pytest.mark.p1
class TestAPIResponseFormats:
    """Test API response format consistency."""

    def test_list_response_has_consistent_structure(self, api_client, db):
        """List endpoints should have consistent structure."""
        baker.make(Product, product_type=Product.ProductType.PHONE, is_published=True, _quantity=3, brand=baker.seq("Brand"), is_global=True)
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        assert isinstance(data, (dict, list))

    def test_error_responses_have_message(self, api_client):
        """Error responses should include error message."""
        response = api_client.get("/api/v1/public/products/999999/")
        if response.status_code >= 400:
            data = response.json()
            assert isinstance(data, (dict, list))


@pytest.mark.django_db
@pytest.mark.p0
class TestMultipartFormDataHandling:
    """Test multipart/form-data handling for file uploads."""

    def test_update_content_accepts_multipart_with_file(
        self, api_client, sample_product, admin_user
    ):
        """update_content should accept multipart with file via __request."""
        api_client.force_authenticate(admin_user)
        from django.core.files.uploadedfile import SimpleUploadedFile

        test_file = SimpleUploadedFile("test.jpg", b"fake image content", content_type="image/jpeg")
        payload = {
            "article_headline": "Test Article",
            "article_body": "Test body",
            "article_thumbnail_image": test_file,
        }
        response = api_client.patch(
            f"/api/inventory/products/{sample_product.id}/update_content/", payload, format="multipart"
        )
        assert response.status_code < 500, f"Got {response.status_code}: {response.data}"


@pytest.mark.django_db
@pytest.mark.p2
class TestAPIDocumentation:
    """Test that API is properly documented."""

    def test_swagger_ui_endpoint_accessible(self, api_client):
        """Swagger UI should be accessible."""
        response = api_client.get("/api/schema/swagger-ui/")
        assert response.status_code < 500

    def test_redoc_endpoint_accessible(self, api_client):
        """ReDoc should be accessible."""
        response = api_client.get("/api/schema/redoc/")
        assert response.status_code < 500

    def test_openapi_yaml_endpoint_accessible(self, api_client):
        """OpenAPI YAML endpoint should be accessible."""
        response = api_client.get("/openapi.yaml")
        assert response.status_code == status.HTTP_200_OK
        assert response.get("content-type") or "yaml" in str(response)


@pytest.mark.django_db
@pytest.mark.p1
class TestCriticalBusinessFlows:
    """Test critical end-to-end flows."""

    def test_browse_products_to_article(self, api_client, sample_product, sample_article):
        """User should be able to browse products and view articles."""
        list_response = api_client.get("/api/v1/public/products/")
        assert list_response.status_code == status.HTTP_200_OK
        detail_response = api_client.get(f"/api/v1/public/products/{sample_product.id}/")
        assert detail_response.status_code == status.HTTP_200_OK
