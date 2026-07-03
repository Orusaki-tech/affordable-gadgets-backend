"""SEO-friendly product slug generation and legacy slug resolution."""

from __future__ import annotations

import re

from django.utils.text import slugify

PRODUCT_TYPE_SUFFIXES = ("ph", "lt", "tb", "ac")
MAX_SEO_SLUG_LENGTH = 60
MAX_SEO_SLUG_TOKENS = 10


def is_missing(value: str | None) -> bool:
    return not value or value.strip() == "" or value.strip().upper() == "N/A"


def normalize_possessives_for_slug(value: str) -> str:
    """
    Normalize possessive apostrophes before slugify so "Apple's" and "Apple s"
    both become the same token sequence (apples, not apple-s).
    """
    text = value or ""
    text = re.sub(r"(\w)'s\b", r"\1s", text, flags=re.IGNORECASE)
    text = re.sub(r"'s\b", "s", text, flags=re.IGNORECASE)
    text = text.replace("'", "")
    return text


def slugify_seo(value: str) -> str:
    """Slugify text with consistent apostrophe / possessive handling."""
    return slugify(normalize_possessives_for_slug(value))


def apostrophe_bug_slug_variants(slug: str) -> set[str]:
    """
    Return slug variants caused by the legacy apostrophe bug.

    Correct: apples-latest-phone
    Buggy:   apple-s-latest-phone
    """
    slug = (slug or "").strip()
    if not slug:
        return set()

    variants = {slug}
    fixed = re.sub(r"([a-z]+)-s-", r"\1s-", slug)
    if fixed != slug:
        variants.add(fixed)
    buggy = re.sub(r"([a-z]+)s-", r"\1-s-", slug)
    if buggy != slug:
        variants.add(buggy)
    return variants


def _slug_tokens(value: str) -> list[str]:
    return [token for token in slugify_seo(value or "").split("-") if token]


def _strip_leading_duplicate_tokens(prefix_tokens: list[str], tokens: list[str]) -> list[str]:
    if not prefix_tokens or not tokens:
        return tokens
    shared = 0
    max_shared = min(len(prefix_tokens), len(tokens))
    while shared < max_shared and prefix_tokens[shared] == tokens[shared]:
        shared += 1
    return tokens[shared:]


def _strip_trailing_type_suffix(slug: str) -> str:
    for suffix in PRODUCT_TYPE_SUFFIXES:
        if slug.endswith(f"-{suffix}"):
            return slug[: -(len(suffix) + 1)]
    return slug


def _trim_slug(slug: str) -> str:
    if len(slug) <= MAX_SEO_SLUG_LENGTH:
        return slug
    tokens = slug.split("-")
    trimmed = "-".join(tokens[:MAX_SEO_SLUG_TOKENS])
    if len(trimmed) <= MAX_SEO_SLUG_LENGTH:
        return trimmed
    return trimmed[:MAX_SEO_SLUG_LENGTH].rstrip("-")


def _merge_tokens(*token_groups: list[str]) -> list[str]:
    merged: list[str] = []
    for group in token_groups:
        for token in group:
            if not token:
                continue
            if merged and merged[-1] == token:
                continue
            if token in merged:
                continue
            merged.append(token)
    return merged


def _primary_descriptor(*, brand: str, model_series: str, product_name: str) -> str:
    candidates: list[tuple[int, str]] = []
    if not is_missing(model_series):
        candidates.append((len(_slug_tokens(model_series)), model_series))
    if not is_missing(product_name):
        candidates.append((len(_slug_tokens(product_name)), product_name))
    if not is_missing(brand):
        candidates.append((len(_slug_tokens(brand)), brand))
    if not candidates:
        return ""
    return max(candidates, key=lambda item: item[0])[1]


def build_seo_product_slug(
    *,
    brand: str = "",
    model_series: str = "",
    product_name: str = "",
    product_type: str = "",
) -> str:
    """
    Build a concise, keyword-focused product slug for SEO.

    Rules:
    - Prefer brand + model descriptor
    - Drop duplicated brand/model/name segments
    - Never append internal product_type codes (PH/LT/TB/AC)
    - Keep slugs short (<= 60 chars when possible)
    """
    del product_type  # intentionally unused

    brand = (brand or "").strip()
    model_series = (model_series or "").strip()
    product_name = (product_name or "").strip()

    if is_missing(brand) and is_missing(model_series) and is_missing(product_name):
        return ""

    brand_tokens = _slug_tokens(brand)
    primary = _primary_descriptor(brand=brand, model_series=model_series, product_name=product_name)
    descriptor_tokens = _strip_leading_duplicate_tokens(brand_tokens, _slug_tokens(primary))

    if not is_missing(product_name) and not is_missing(model_series):
        name_tokens = _strip_leading_duplicate_tokens(
            descriptor_tokens,
            _strip_leading_duplicate_tokens(brand_tokens, _slug_tokens(product_name)),
        )
        extra_tokens = [token for token in name_tokens if token not in descriptor_tokens]
        if extra_tokens and len(extra_tokens) <= 4:
            descriptor_tokens = _merge_tokens(descriptor_tokens, extra_tokens)

    if brand_tokens:
        slug_tokens = _merge_tokens(brand_tokens, descriptor_tokens)
    else:
        slug_tokens = descriptor_tokens

    slug = "-".join(slug_tokens)
    slug = _strip_trailing_type_suffix(slug)

    if not slug:
        fallback = product_name or model_series or brand
        slug = slugify_seo(fallback)

    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return _trim_slug(slug)


def allocate_unique_slugs(
    proposals: list[tuple[int, str]],
    *,
    reserved: set[str] | None = None,
) -> dict[int, str]:
    """
    Assign unique slugs to (product_id, base_slug) proposals.

    On collision, append a numeric suffix (-2, -3, ...).
    """
    reserved = set(reserved or ())
    assigned: dict[int, str] = {}
    used = set(reserved)

    for product_id, base_slug in proposals:
        if not base_slug:
            continue
        candidate = base_slug
        counter = 2
        while candidate in used:
            candidate = f"{base_slug}-{counter}"
            counter += 1
            candidate = _trim_slug(candidate)
        assigned[product_id] = candidate
        used.add(candidate)

    return assigned


def resolve_product_for_slug(slug: str, queryset=None):
    """
    Resolve a storefront slug to a Product.

    Returns (product, is_legacy_redirect).
    """
    from inventory.models import Product, ProductSlugRedirect

    if not slug:
        return None, False

    if queryset is None:
        queryset = Product.objects.filter(is_discontinued=False, is_published=True)

    product = queryset.filter(slug=slug).first()
    if product:
        return product, False

    redirect_entry = (
        ProductSlugRedirect.objects.filter(old_slug=slug)
        .select_related("product")
        .order_by("-created_at")
        .first()
    )
    if not redirect_entry:
        return None, False

    product = redirect_entry.product
    if product.is_discontinued or not product.is_published:
        return None, False

    if queryset is not None:
        if not queryset.filter(pk=product.pk).exists():
            return None, False

    return product, True


def resolve_article_for_slug(product, slug: str):
    """
    Resolve a published article slug under a product.

    Returns (article, is_legacy_redirect).
    """
    from inventory.models import ProductArticle, ProductArticleSlugRedirect

    if not product or not slug:
        return None, False

    article = (
        ProductArticle.objects.filter(product=product, slug=slug, is_published=True)
        .select_related("product")
        .first()
    )
    if article:
        return article, False

    redirect_entry = (
        ProductArticleSlugRedirect.objects.filter(product=product, old_slug=slug)
        .select_related("article", "article__product")
        .order_by("-created_at")
        .first()
    )
    if not redirect_entry:
        return None, False

    article = redirect_entry.article
    if not article.is_published or not article.product.is_published:
        return None, False
    return article, True
