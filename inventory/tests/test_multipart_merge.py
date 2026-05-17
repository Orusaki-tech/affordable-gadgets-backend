# Test multipart merge handling

import io
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from model_bakery import baker
from inventory.models import Product, ProductArticle

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def admin_user(db):
    return baker.make('auth.User', is_staff=True, is_superuser=True)

@pytest.fixture
def sample_product(db):
    return baker.make(Product, product_name='Test Product', is_published=True)

@pytest.mark.django_db
def test_mixed_multipart_and_json_payload(api_client, admin_user, sample_product):
    """Send a multipart request that includes both flattened article fields
    and a nested JSON article payload. Verify that the view merges correctly
    and that the thumbnail image from FILES wins over any JSON value.
    """
    api_client.force_authenticate(admin_user)

    # Simulate a file upload for thumbnail
    thumb_file = SimpleUploadedFile('thumb.jpg', b'fake-image-data', content_type='image/jpeg')

    # Build multipart payload: flattened keys for headline & thumbnail, and a nested JSON article dict for body
    payload = {
        'article_headline': 'Flattened Headline',
        'article_thumbnail_image': thumb_file,
        # Provide a JSON article dict as a string – DRF will treat it as a regular field
        'article': '{"body": "JSON body", "seo_title": "JSON SEO"}',
    }

    response = api_client.patch(
        f'/api/inventory/products/{sample_product.id}/update_content/',
        payload,
        format='multipart',
    )

    assert response.status_code == 200, response.content
    data = response.json()
    # The response should reflect merged article data
    article = data.get('article')
    assert article is not None
    # Flattened headline should win over any JSON value (none in JSON)
    assert article.get('headline') == 'Flattened Headline'
    # Thumbnail should be present (URL string) – ensure file handling didn't error
    assert 'thumbnail_image' in article and isinstance(article['thumbnail_image'], str)
    # JSON-provided fields should be present as they were not overridden
    assert article.get('body') == 'JSON body'
    assert article.get('seo_title') == 'JSON SEO'
