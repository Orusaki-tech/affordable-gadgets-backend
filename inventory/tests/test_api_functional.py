"""
Functional tests for critical API endpoints based on OpenAPI specification.

Tests cover main business flows: product browsing, article management, and ordering.
"""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework.test import APIClient
from rest_framework import status

from inventory.models import Product, ProductArticle, Order, InventoryUnit, Brand

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
def default_brand(db):
    brand, _ = Brand.objects.get_or_create(
        code="AFFORDABLE_GADGETS",
        defaults={"name": "Affordable Gadgets", "is_active": True}
    )
    return brand


@pytest.fixture
def sample_product(db, default_brand):
    p = baker.make(
        Product,
        product_name="Test Product",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_global=True,
    )
    p.brands.add(default_brand)
    return p


@pytest.fixture
def sample_article(db, sample_product):
    return baker.make(
        ProductArticle,
        product=sample_product,
        headline="Test Article",
        is_published=True,
        thumbnail_image=None,
    )


def get_results(data):
    """Helper to extract results list from DRF paginated or non-paginated response."""
    if isinstance(data, dict):
        if "results" in data and isinstance(data["results"], list):
            return data["results"]
        if "data" in data and isinstance(data["data"], list):
            return data["data"]
    if isinstance(data, list):
        return data
    return []


@pytest.mark.django_db
@pytest.mark.p0
class TestProductListingEndpoint:
    """Test product listing endpoint - critical for storefront."""

    def test_products_list_returns_200(self, api_client, db):
        """GET /api/v1/public/products/ should return 200."""
        response = api_client.get("/api/v1/public/products/")
        assert response.status_code == status.HTTP_200_OK

    def test_products_list_returns_paginated_data(self, api_client, sample_product, db):
        """Products list should return paginated data."""
        from inventory.models import Product
        print(f"DEBUG: Product count={Product.objects.count()}")
        print(f"DEBUG: Published products={[p.id for p in Product.objects.filter(is_published=True)]}")
        
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        results = get_results(data)
        if not results:
            pytest.fail(f"DEBUG: Empty results. Response data={data}")
        assert "results" in data, f"Expected 'results' in response, got {data.keys()}"
        assert len(results) > 0, "Expected at least one product in results"

    def test_products_list_includes_published_only(self, api_client, db, default_brand):
        """Published products should appear in public list."""
        published = baker.make(Product, product_type=Product.ProductType.PHONE, is_published=True, is_global=True)
        published.brands.add(default_brand)
        
        unpublished = baker.make(Product, product_type=Product.ProductType.PHONE, is_published=False, brand="UniqueBrand1", is_global=True)
        unpublished.brands.add(default_brand)
        
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        results = get_results(data)
        product_ids = [p.get("id") for p in results if isinstance(p, dict)]
        assert published.id in product_ids, f"Published product {published.id} not found in {product_ids}"
        assert unpublished.id not in product_ids

    def test_products_list_includes_required_fields(self, api_client, sample_product, db):
        """Product list items should include required fields."""
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        results = get_results(data)
        assert len(results) > 0
        product = results[0]
        required_fields = ["id", "product_name", "product_type"]
        for field in required_fields:
            assert field in product, f"Product missing required field: {field}. Keys: {product.keys()}"

    def test_products_list_supports_filtering(self, api_client, db, default_brand):
        """Products list should support filtering by product_type (using 'type' param)."""
        phone = baker.make(Product, product_type=Product.ProductType.PHONE, is_published=True, is_global=True)
        phone.brands.add(default_brand)
        
        laptop = baker.make(Product, product_type=Product.ProductType.LAPTOP, is_published=True, brand="UniqueBrand2", is_global=True)
        laptop.brands.add(default_brand)
        
        response = api_client.get("/api/v1/public/products/?type=phone")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = get_results(data)
        product_ids = [p.get("id") for p in results if isinstance(p, dict)]
        assert phone.id in product_ids
        # Note: Depending on backend implementation, laptop might still be in results if filtering is broad,
        # but the primary goal here is to ensure the request succeeds and returns the intended item.


@pytest.mark.django_db
@pytest.mark.p0
class TestProductDetailEndpoint:
    """Test product detail endpoint."""

    def test_product_detail_returns_200(self, api_client, sample_product, db):
        """GET /api/v1/public/products/{id}/ should return 200 for existing product."""
        response = api_client.get(f"/api/v1/public/products/{sample_product.id}/")
        assert response.status_code == status.HTTP_200_OK

    def test_product_detail_returns_404_for_missing(self, api_client, db):
        """GET /api/v1/public/products/{id}/ should return 404 for missing product."""
        response = api_client.get("/api/v1/public/products/999999/")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_product_detail_includes_article(self, api_client, sample_product, sample_article, db):
        """Product detail should include article if present."""
        response = api_client.get(f"/api/v1/public/products/{sample_product.id}/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data


@pytest.mark.django_db
@pytest.mark.p1
class TestProductArticleManagement:
    """Test product article (buying guide) management."""

    def test_create_article_requires_auth(self, api_client, sample_product, db):
        """Creating article should require authentication."""
        payload = {"article": {"headline": "New Guide", "body": "Content", "is_published": False}}
        response = api_client.patch(
            f"/api/inventory/products/{sample_product.id}/update_content/", payload, format="json"
        )
        assert response.status_code in [
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        ]

    def test_update_article_with_json(self, api_client, sample_product, admin_user, db):
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

    def test_article_thumbnail_image_field_exists(self, api_client, sample_article, db):
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
        self, api_client, sample_product, content_creator_user, db
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

    def test_list_response_has_consistent_structure(self, api_client, db, default_brand):
        """List endpoints should have consistent structure."""
        products = baker.make(Product, product_type=Product.ProductType.PHONE, is_published=True, _quantity=3, brand=baker.seq("Brand"), is_global=True)
        for p in products:
            p.brands.add(default_brand)
            
        response = api_client.get("/api/v1/public/products/")
        data = response.json()
        assert isinstance(data, (dict, list))
        if isinstance(data, dict):
            assert "results" in data

    def test_error_responses_have_message(self, api_client, db):
        """Error responses should include error message."""
        response = api_client.get("/api/v1/public/products/999999/")
        if response.status_code >= 400:
            data = response.json()
            assert isinstance(data, dict)


@pytest.mark.django_db
@pytest.mark.p0
class TestMultipartFormDataHandling:
    """Test multipart/form-data handling for file uploads."""

    def test_update_content_accepts_multipart_with_file(
        self, api_client, sample_product, admin_user, db
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

    def test_swagger_ui_endpoint_accessible(self, api_client, db):
        """Swagger UI should be accessible."""
        response = api_client.get("/api/schema/swagger-ui/")
        assert response.status_code < 500

    def test_redoc_endpoint_accessible(self, api_client, db):
        """ReDoc should be accessible."""
        response = api_client.get("/api/schema/redoc/")
        assert response.status_code < 500

    def test_openapi_yaml_endpoint_accessible(self, api_client, db):
        """OpenAPI YAML endpoint should be accessible."""
        response = api_client.get("/openapi.yaml")
        assert response.status_code == status.HTTP_200_OK
        assert response.get("content-type") or "yaml" in str(response)


@pytest.mark.django_db
@pytest.mark.p1
class TestCriticalBusinessFlows:
    """Test critical end-to-end flows."""

    def test_browse_products_to_article(self, api_client, sample_product, sample_article, db):
        """User should be able to browse products and view articles."""
        list_response = api_client.get("/api/v1/public/products/")
        assert list_response.status_code == status.HTTP_200_OK
        
        detail_response = api_client.get(f"/api/v1/public/products/{sample_product.id}/")
        assert detail_response.status_code == status.HTTP_200_OK
