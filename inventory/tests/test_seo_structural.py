import pytest
from model_bakery import baker

from inventory.models import Product, ProductArticle, ProductArticleSlugRedirect, ProductSlugRedirect
from inventory.seo_structural import (
    consolidate_duplicate_products,
    deduplicate_product_articles,
    detect_article_mismatches,
    extract_model_from_headline,
    extract_model_tokens_from_slug,
    fix_apostrophe_article_slugs,
    reparent_product_articles,
)
from inventory.slug_utils import (
    apostrophe_bug_slug_variants,
    resolve_article_for_slug,
    resolve_product_for_slug,
    slugify_seo,
)


def test_slugify_seo_normalizes_possessives():
    assert slugify_seo("Apple's Latest Phone") == "apples-latest-phone"
    assert slugify_seo("Apple s Latest Phone") == "apples-latest-phone"


def test_apostrophe_bug_slug_variants():
    variants = apostrophe_bug_slug_variants("apple-s-latest-phone")
    assert "apples-latest-phone" in variants
    assert "apple-s-latest-phone" in variants


@pytest.mark.django_db
def test_resolve_article_for_slug_uses_redirect():
    product = baker.make(
        Product,
        slug="apple-iphone-15",
        product_name="iPhone 15",
        brand="Apple",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=product,
        slug="apples-latest-phone",
        headline="Apple's Latest Phone",
        is_published=True,
    )
    ProductArticleSlugRedirect.objects.create(
        product=product,
        old_slug="apple-s-latest-phone",
        article=article,
    )

    resolved, legacy = resolve_article_for_slug(product, "apple-s-latest-phone")
    assert legacy is True
    assert resolved == article


@pytest.mark.django_db
def test_consolidate_duplicate_products_unpublishes_suffix_duplicate():
    canonical = baker.make(
        Product,
        slug="samsung-galaxy-s25",
        product_name="Samsung Galaxy S25",
        brand="Samsung",
        model_series="Galaxy S25",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    dupe = baker.make(
        Product,
        slug="samsung-galaxy-s25-2",
        product_name="Samsung Galaxy S25",
        brand="Samsung",
        model_series="Galaxy S25 256GB",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )

    stats = consolidate_duplicate_products(dry_run=False)

    dupe.refresh_from_db()
    redirect = ProductSlugRedirect.objects.get(old_slug="samsung-galaxy-s25-2")
    assert dupe.is_published is False
    assert redirect.product_id == canonical.id
    assert stats.created >= 1


@pytest.mark.django_db
def test_reparent_product_articles_moves_mismatched_iphone_post():
    wrong_parent = baker.make(
        Product,
        slug="apple-iphone-13-sim",
        product_name="iPhone 13 SIM",
        brand="Apple",
        model_series="iPhone 13",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    right_parent = baker.make(
        Product,
        slug="apple-iphone-15-pro-sim",
        product_name="iPhone 15 Pro SIM",
        brand="Apple",
        model_series="iPhone 15 Pro",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=wrong_parent,
        slug="iphone-15-pro-review-the-pro-iphone-that-does-it-all",
        headline="iPhone 15 Pro Review: still worth it in 2026",
        is_published=True,
    )

    assert extract_model_from_headline(article.headline, brand="Apple") == "15 pro"
    assert "15" in extract_model_tokens_from_slug(article.slug)

    stats = reparent_product_articles(dry_run=False, auto_detect=True)
    article.refresh_from_db()

    assert article.product_id == right_parent.id
    assert stats.updated >= 1


@pytest.mark.django_db
def test_reparent_leaves_correct_iphone_13_review_on_iphone_13():
    parent = baker.make(
        Product,
        slug="apple-iphone-13-sim",
        product_name="iPhone 13 SIM",
        brand="Apple",
        model_series="iPhone 13",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    other = baker.make(
        Product,
        slug="apple-iphone-15-sim",
        product_name="iPhone 15 SIM",
        brand="Apple",
        model_series="iPhone 15",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=parent,
        slug="iphone-13-review-why-its-still-a-great-buy-in-2026",
        headline="iPhone 13 Review: Why It's Still a Great Buy in 2026",
        is_published=True,
    )

    stats = reparent_product_articles(dry_run=False, auto_detect=True)
    article.refresh_from_db()

    assert article.product_id == parent.id
    assert stats.updated == 0


@pytest.mark.django_db
def test_reparent_moves_pixel_8_off_pixel_10():
    wrong_parent = baker.make(
        Product,
        slug="google-pixel-10",
        product_name="Google Pixel 10",
        brand="Google",
        model_series="Pixel 10",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    right_parent = baker.make(
        Product,
        slug="google-pixel-8",
        product_name="Google Pixel 8",
        brand="Google",
        model_series="Pixel 8",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=wrong_parent,
        slug="google-pixel-8-review",
        headline="Google Pixel 8 Review",
        is_published=True,
    )

    stats = reparent_product_articles(dry_run=False, auto_detect=True)
    article.refresh_from_db()

    assert article.product_id == right_parent.id
    assert stats.updated >= 1


@pytest.mark.django_db
def test_reparent_moves_galaxy_s10_phone_off_tab_s10_fe():
    wrong_parent = baker.make(
        Product,
        slug="samsung-galaxy-tab-s10-fe-wifi",
        product_name="Galaxy Tab S10 FE WiFi",
        brand="Samsung",
        model_series="Galaxy Tab S10 FE",
        product_type=Product.ProductType.TABLET,
        is_published=True,
        is_discontinued=False,
    )
    right_parent = baker.make(
        Product,
        slug="samsung-galaxy-s10",
        product_name="Samsung Galaxy S10",
        brand="Samsung",
        model_series="Galaxy S10",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=wrong_parent,
        slug="samsung-galaxy-s10-review",
        headline="Samsung Galaxy S10 Review",
        is_published=True,
    )

    stats = reparent_product_articles(dry_run=False, auto_detect=True)
    article.refresh_from_db()

    assert article.product_id == right_parent.id
    assert stats.updated >= 1


@pytest.mark.django_db
def test_reparent_moves_z_flip_5_off_z_flip_5_duplicate_host():
    wrong_parent = baker.make(
        Product,
        slug="samsung-galaxy-z-flip-5-2",
        product_name="Galaxy Z Flip 5 duplicate",
        brand="Samsung",
        model_series="Galaxy Z Flip 5 duplicate host",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    right_parent = baker.make(
        Product,
        slug="samsung-galaxy-z-flip-5",
        product_name="Samsung Galaxy Z Flip 5",
        brand="Samsung",
        model_series="Galaxy Z Flip 5",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=wrong_parent,
        slug="samsung-galaxy-z-flip-5-review",
        headline="Samsung Galaxy Z Flip 5 Review",
        is_published=True,
    )

    stats = reparent_product_articles(dry_run=False, auto_detect=True)
    article.refresh_from_db()

    assert article.product_id == right_parent.id
    assert stats.updated >= 1


@pytest.mark.django_db
def test_reparent_moves_airpods_pro_3_off_airpods_4():
    wrong_parent = baker.make(
        Product,
        slug="apple-airpods-4",
        product_name="AirPods 4",
        brand="Apple",
        model_series="AirPods 4",
        product_type=Product.ProductType.ACCESSORY,
        is_published=True,
        is_discontinued=False,
    )
    right_parent = baker.make(
        Product,
        slug="apple-airpods-pro-3",
        product_name="AirPods Pro 3",
        brand="Apple",
        model_series="AirPods Pro 3",
        product_type=Product.ProductType.ACCESSORY,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=wrong_parent,
        slug="airpods-pro-3-review",
        headline="AirPods Pro 3 Review",
        is_published=True,
    )

    stats = reparent_product_articles(dry_run=False, auto_detect=True)
    article.refresh_from_db()

    assert article.product_id == right_parent.id
    assert stats.updated >= 1


@pytest.mark.django_db
def test_detect_article_mismatches_flags_wrong_parent():
    wrong_parent = baker.make(
        Product,
        slug="samsung-galaxy-s25-ultra",
        product_name="Galaxy S25 Ultra",
        brand="Samsung",
        model_series="Galaxy S25 Ultra",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    right_parent = baker.make(
        Product,
        slug="samsung-galaxy-s20-ultra",
        product_name="Galaxy S20 Ultra",
        brand="Samsung",
        model_series="Galaxy S20 Ultra",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=wrong_parent,
        slug="samsung-galaxy-s20-ultra-review",
        headline="Samsung Galaxy S20 Ultra Review",
        is_published=True,
    )

    mismatches = detect_article_mismatches(min_confidence=0.5)
    matched = [row for row in mismatches if row.article_id == article.id]

    assert matched
    assert matched[0].suggested_product_slug == right_parent.slug


@pytest.mark.django_db
def test_deduplicate_product_articles_keeps_canonical_copy():
    canonical_product = baker.make(
        Product,
        slug="samsung-a-series-galaxy-a06",
        product_name="Galaxy A06",
        brand="Samsung",
        model_series="Galaxy A06",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    dupe_product = baker.make(
        Product,
        slug="samsung-galaxy-a16",
        product_name="Galaxy A16",
        brand="Samsung",
        model_series="Galaxy A16",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    keeper = ProductArticle.objects.create(
        product=dupe_product,
        slug="galaxy-a16-review",
        headline="Galaxy A16 review",
        body="Same body",
        is_published=True,
    )
    ProductArticle.objects.create(
        product=canonical_product,
        slug="galaxy-a16-review",
        headline="Galaxy A16 review",
        body="Same body",
        is_published=True,
    )

    stats = deduplicate_product_articles(dry_run=False)

    assert ProductArticle.objects.filter(slug="galaxy-a16-review").count() == 1
    assert ProductArticle.objects.get(slug="galaxy-a16-review").id == keeper.id
    assert stats.deleted >= 1


@pytest.mark.django_db
def test_fix_apostrophe_article_slugs_creates_redirect():
    product = baker.make(
        Product,
        slug="apple-iphone-15",
        product_name="iPhone 15",
        brand="Apple",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=product,
        slug="apple-s-latest-phone",
        headline="Apple's Latest Phone",
        is_published=True,
    )

    stats = fix_apostrophe_article_slugs(dry_run=False)
    article.refresh_from_db()
    redirect = ProductArticleSlugRedirect.objects.get(old_slug="apple-s-latest-phone")

    assert article.slug == "apples-latest-phone"
    assert redirect.article_id == article.id
    assert stats.updated >= 1


@pytest.mark.django_db
def test_resolve_product_for_slug_uses_redirect():
    product = baker.make(
        Product,
        slug="samsung-galaxy-a57",
        product_name="Samsung Galaxy A57",
        brand="Samsung",
        model_series="Galaxy A57",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    ProductSlugRedirect.objects.create(old_slug="samsung-galaxy-a57-samsung-galaxy-a57-ph", product=product)

    resolved, legacy = resolve_product_for_slug(
        "samsung-galaxy-a57-samsung-galaxy-a57-ph",
        queryset=Product.objects.filter(is_published=True, is_discontinued=False),
    )
    assert legacy is True
    assert resolved == product

    canonical, legacy = resolve_product_for_slug(
        "samsung-galaxy-a57",
        queryset=Product.objects.filter(is_published=True, is_discontinued=False),
    )
    assert legacy is False
    assert canonical == product
