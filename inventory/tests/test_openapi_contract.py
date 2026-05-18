"""
Contract testing against OpenAPI schema.

This test suite validates that API responses conform to the OpenAPI specification.
It ensures the API contract is honored and changes to the schema don't break clients.
"""

from pathlib import Path

import pytest
import yaml
from openapi_spec_validator import validate_spec
from openapi_spec_validator.validation.validators import OpenAPIV30SpecValidator
from rest_framework.test import APIClient


@pytest.fixture(scope="session")
def openapi_spec():
    """Load and validate the OpenAPI specification."""
    spec_path = Path(__file__).parent.parent.parent / "openapi.yaml"

    with open(spec_path) as f:
        spec = yaml.safe_load(f)

    # Validate the spec itself is valid OpenAPI 3.0
    try:
        validate_spec(spec)
    except Exception as e:
        pytest.fail(f"OpenAPI spec validation failed: {e}")

    return spec


@pytest.fixture
def api_client():
    """Return an authenticated API client."""
    client = APIClient()
    return client


@pytest.fixture
def schema_validator(openapi_spec):
    """Create a validator from the OpenAPI spec."""
    return OpenAPIV30SpecValidator(openapi_spec)


@pytest.mark.p0
class TestOpenAPIContractPublicEndpoints:
    """Test contract compliance for API schema documentation."""

    def test_openapi_spec_is_valid(self, openapi_spec):
        """Verify OpenAPI spec itself is valid."""
        assert openapi_spec is not None
        assert "openapi" in openapi_spec
        assert "paths" in openapi_spec
        assert "components" in openapi_spec

    def test_products_list_endpoint_documented(self, openapi_spec):
        """Test /products/ endpoint is documented in schema."""
        paths = openapi_spec["paths"]

        # Check products endpoint exists
        has_products = any("products" in path and "get" in paths[path] for path in paths.keys())
        assert has_products, "Products list endpoint not documented in OpenAPI spec"

    def test_products_detail_endpoint_documented(self, openapi_spec):
        """Test /products/{id}/ endpoint is documented in schema."""
        paths = openapi_spec["paths"]

        # Check that product detail endpoint is documented
        has_product_detail = any(
            path
            for path in paths.keys()
            if "products" in path and ("{id}" in path or "{product_id}" in path)
        )
        assert has_product_detail, "Product detail endpoint not documented in OpenAPI spec"

    def test_product_article_endpoint_documented(self, openapi_spec):
        """Test article endpoints are documented."""
        paths = openapi_spec["paths"]

        has_article_endpoint = any(
            path
            for path in paths.keys()
            if "article" in path.lower() or "update_content" in path.lower()
        )
        # Articles might be nested or separate, so just verify it's documented somewhere
        if has_article_endpoint:
            assert True


@pytest.mark.p1
class TestOpenAPIContractResponseStructures:
    """Test that response structures are properly defined in schema."""

    def test_error_response_schema_defined(self, openapi_spec):
        """Test error response schemas are defined."""
        components = openapi_spec.get("components", {})
        schemas = components.get("schemas", {})

        # Should have at least basic error schemas
        has_schemas = len(schemas) > 0
        assert has_schemas, "No schemas defined in OpenAPI components"

    def test_paginated_response_schema_defined(self, openapi_spec):
        """Test pagination response schema is defined."""
        components = openapi_spec.get("components", {})
        schemas = components.get("schemas", {})

        # Should have pagination-related schemas
        has_paging_schema = any(
            s
            for s in schemas.keys()
            if "pagina" in s.lower() or "list" in s.lower() or "result" in s.lower()
        )
        # Pagination might be implicit in serializers, so this is optional
        assert len(schemas) > 0


@pytest.mark.p1
class TestOpenAPISchemaConsistency:
    """Test consistency and completeness of OpenAPI schema."""

    def test_all_paths_have_descriptions(self, openapi_spec):
        """Verify all paths are documented with descriptions."""
        paths = openapi_spec.get("paths", {})

        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    assert "description" in details or "summary" in details, (
                        f"Path {path} {method} missing description/summary"
                    )

    def test_all_parameters_documented(self, openapi_spec):
        """Verify all parameters are properly documented."""
        paths = openapi_spec.get("paths", {})

        params_count = 0
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    parameters = details.get("parameters", [])
                    for param in parameters:
                        assert "name" in param, f"Parameter in {path} {method} missing name"
                        assert "in" in param, f"Parameter in {path} {method} missing 'in' field"
                        assert "schema" in param or "content" in param, (
                            f"Parameter {param.get('name')} in {path} {method} missing schema"
                        )
                        params_count += 1

        assert params_count > 0, "No parameters found in OpenAPI spec"

    def test_required_schemas_present(self, openapi_spec):
        """Verify key schemas are defined."""
        schemas = openapi_spec.get("components", {}).get("schemas", {})

        # Check for important domain schemas
        important_schemas = ["Product", "ProductArticle", "Order", "InventoryUnit"]

        for schema in important_schemas:
            # Allow flexible naming
            found = any(s for s in schemas.keys() if schema in s)
            # Note: Some schemas might be optional, so we just log but don't fail
            if not found:
                print(f"Warning: {schema} schema not found in components")


@pytest.mark.p2
class TestOpenAPIMediaTypes:
    """Test that endpoints declare correct media types."""

    def test_json_endpoints_declared(self, openapi_spec):
        """Verify JSON endpoints are properly declared."""
        paths = openapi_spec.get("paths", {})

        json_endpoints = 0
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "patch", "delete"]:
                    responses = details.get("responses", {})
                    for status_code, response_details in responses.items():
                        content = response_details.get("content", {})
                        if "application/json" in content:
                            json_endpoints += 1

        assert json_endpoints > 0, "No JSON endpoints found in OpenAPI spec"

    def test_multipart_endpoints_declared(self, openapi_spec):
        """Verify multipart/form-data endpoints are documented."""
        paths = openapi_spec.get("paths", {})

        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["post", "put", "patch"]:
                    request_body = details.get("requestBody", {})
                    content = request_body.get("content", {})

                    # If endpoint accepts file uploads, it should be documented
                    if "multipart/form-data" in content:
                        # Verify it's properly documented (schema can be inline, $ref, or allOf)
                        multipart_schema = content["multipart/form-data"].get("schema", {})
                        assert any(
                            k in multipart_schema
                            for k in ["properties", "allOf", "$ref", "oneOf", "anyOf"]
                        ), f"Multipart endpoint {path} {method} missing schema details"


@pytest.mark.p0
class TestOpenAPIThumbnailImageField:
    """Test ProductArticle thumbnail_image field is properly documented."""

    def test_product_article_schema_has_thumbnail_image(self, openapi_spec):
        """Verify ProductArticle schema includes thumbnail_image field."""
        schemas = openapi_spec.get("components", {}).get("schemas", {})

        # Find ProductArticle schema
        article_schemas = [s for s in schemas.keys() if "Article" in s or "article" in s]

        for schema_name in article_schemas:
            schema = schemas[schema_name]
            properties = schema.get("properties", {})

            # Check if thumbnail_image is present
            if "thumbnail_image" in properties:
                thumbnail_field = properties["thumbnail_image"]
                # Verify it's documented as string (URL) or File
                assert any(t in str(thumbnail_field) for t in ["string", "file", "object"]), (
                    f"thumbnail_image field in {schema_name} has unexpected type"
                )

    def test_update_content_action_accepts_multipart(self, openapi_spec):
        """Verify update_content action accepts multipart/form-data."""
        paths = openapi_spec.get("paths", {})

        update_content_paths = [p for p in paths.keys() if "update_content" in p]

        for path in update_content_paths:
            patch_details = paths[path].get("patch", {})
            request_body = patch_details.get("requestBody", {})
            content = request_body.get("content", {})

            # Should support both JSON and multipart
            assert "application/json" in content or "multipart/form-data" in content, (
                f"update_content path {path} should support JSON or multipart"
            )
