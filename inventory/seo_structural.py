"""SEO structural maintenance: duplicate URLs, misassigned blogs, apostrophe slugs."""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction
from django.utils.text import slugify

from inventory.models import Product, ProductArticle, ProductArticleSlugRedirect, ProductSlugRedirect
from inventory.slug_utils import (
    apostrophe_bug_slug_variants,
    build_seo_product_slug,
    slugify_seo,
)

NUMERIC_SLUG_SUFFIX_RE = re.compile(r"-\d+$")
IPHONE_MODEL_RE = re.compile(
    r"\biphone\s+(\d+\s*(?:pro\s*max|pro|plus|mini|e|air)?)\b",
    re.IGNORECASE,
)
GALAXY_MODEL_RE = re.compile(
    r"\b(galaxy\s+[a-z]?\d+[^\s,.:;)]*|galaxy\s+z\s+\w+[^\s,.:;)]*)\b",
    re.IGNORECASE,
)


@dataclass
class MaintenanceStats:
    scanned: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0
    notes: list[str] = field(default_factory=list)


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _slug_base(slug: str) -> str:
    slug = (slug or "").strip()
    while True:
        stripped = NUMERIC_SLUG_SUFFIX_RE.sub("", slug)
        if stripped == slug:
            return stripped
        slug = stripped


def _products_compatible(a: Product, b: Product) -> bool:
    if (a.brand or "").strip().lower() != (b.brand or "").strip().lower():
        return False
    left = _normalize_name(a.product_name)
    right = _normalize_name(b.product_name)
    if not left or not right:
        return False
    if left == right or left in right or right in left:
        return True
    left_tokens = set(slugify_seo(left).split("-")) - {"", "gb", "ram", "tb"}
    right_tokens = set(slugify_seo(right).split("-")) - {"", "gb", "ram", "tb"}
    overlap = left_tokens & right_tokens
    return len(overlap) >= 2 or (
        len(overlap) >= 1 and any(re.search(r"\d", token) for token in overlap)
    )


def _canonical_product_score(product: Product) -> tuple:
    seo_slug = build_seo_product_slug(
        brand=product.brand,
        model_series=product.model_series,
        product_name=product.product_name,
        product_type=product.product_type,
    )
    slug = (product.slug or "").strip()
    slug_matches_seo = slug == seo_slug
    no_numeric_suffix = not NUMERIC_SLUG_SUFFIX_RE.search(slug)
    article_count = product.articles.filter(is_published=True).count()
    unit_count = product.inventory_units.count()
    return (
        int(slug_matches_seo),
        int(no_numeric_suffix),
        article_count,
        unit_count,
        int(product.is_published),
        -product.id,
    )


def pick_canonical_product(products: list[Product]) -> Product:
    return max(products, key=_canonical_product_score)


def extract_model_from_headline(headline: str, brand: str = "") -> str | None:
    text = headline or ""
    brand_lower = (brand or "").strip().lower()
    if brand_lower in {"", "apple"} or "iphone" in text.lower():
        match = IPHONE_MODEL_RE.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip().lower())
    if brand_lower in {"", "samsung"} or "galaxy" in text.lower():
        match = GALAXY_MODEL_RE.search(text)
        if match:
            return re.sub(r"\s+", " ", match.group(1).strip().lower())
    return None


def find_product_for_model(model_key: str, *, brand: str, product_type: str = "PH") -> Product | None:
    if not model_key:
        return None
    model_slug = slugify_seo(model_key)
    if not model_slug:
        return None

    candidates = list(
        Product.objects.filter(
            brand__iexact=brand,
            product_type=product_type,
            is_discontinued=False,
            is_published=True,
        ).order_by("id")
    )
    scored: list[tuple[tuple, Product]] = []
    for product in candidates:
        product_slug = (product.slug or "").strip()
        haystack = " ".join(
            filter(
                None,
                [
                    product_slug,
                    slugify_seo(product.product_name),
                    slugify_seo(product.model_series),
                ],
            )
        )
        if model_slug not in haystack and model_slug.replace("-", "") not in haystack.replace("-", ""):
            continue
        scored.append((_canonical_product_score(product), product))
    if not scored:
        return None
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1]


def consolidate_duplicate_products(
    *,
    dry_run: bool = False,
    explicit_pairs: list[tuple[str, str]] | None = None,
) -> MaintenanceStats:
    """
    Pick one canonical product per duplicate cluster and 301-redirect / unpublish the rest.

    explicit_pairs: list of (duplicate_slug, canonical_slug)
    """
    stats = MaintenanceStats()
    products = list(
        Product.objects.filter(is_discontinued=False, is_published=True).prefetch_related("articles")
    )
    stats.scanned = len(products)
    by_slug = {(p.slug or "").strip(): p for p in products if p.slug}
    clusters: dict[str, list[Product]] = defaultdict(list)

    for product in products:
        slug = (product.slug or "").strip()
        if not slug:
            continue
        clusters[_slug_base(slug)].append(product)

    actions: list[tuple[Product, Product, str]] = []

    for _base, group in clusters.items():
        if len(group) < 2:
            continue
        compatible_groups: list[list[Product]] = []
        for product in group:
            placed = False
            for cluster in compatible_groups:
                if any(_products_compatible(product, other) for other in cluster):
                    cluster.append(product)
                    placed = True
                    break
            if not placed:
                compatible_groups.append([product])
        for cluster in compatible_groups:
            if len(cluster) < 2:
                continue
            canonical = pick_canonical_product(cluster)
            for dupe in cluster:
                if dupe.id == canonical.id:
                    continue
                if not _products_compatible(dupe, canonical):
                    stats.skipped += 1
                    continue
                actions.append((dupe, canonical, "cluster"))

    for old_slug, new_slug in explicit_pairs or []:
        dupe = by_slug.get(old_slug)
        canonical = by_slug.get(new_slug)
        if dupe and canonical and dupe.id != canonical.id:
            actions.append((dupe, canonical, "explicit"))

    seen_dupe_ids: set[int] = set()
    deduped_actions: list[tuple[Product, Product, str]] = []
    for dupe, canonical, source in actions:
        if dupe.id in seen_dupe_ids:
            continue
        seen_dupe_ids.add(dupe.id)
        deduped_actions.append((dupe, canonical, source))

    existing_redirects = {
        row.old_slug: row.product_id
        for row in ProductSlugRedirect.objects.values("old_slug", "product_id")
    }

    redirects_to_create: list[ProductSlugRedirect] = []
    to_unpublish: list[Product] = []

    for dupe, canonical, source in deduped_actions:
        old_slug = (dupe.slug or "").strip()
        new_slug = (canonical.slug or "").strip()
        if not old_slug or old_slug == new_slug:
            stats.skipped += 1
            continue
        if old_slug in by_slug and by_slug[old_slug].id not in {canonical.id, dupe.id}:
            stats.skipped += 1
            stats.notes.append(f"skip {old_slug}: live slug owned by another product")
            continue
        if old_slug in existing_redirects and existing_redirects[old_slug] != canonical.id:
            stats.skipped += 1
            stats.notes.append(f"skip {old_slug}: redirect conflict")
            continue
        stats.notes.append(f"[{source}] {old_slug} -> {new_slug} (unpublish id={dupe.id})")
        redirects_to_create.append(ProductSlugRedirect(old_slug=old_slug, product_id=canonical.id))
        to_unpublish.append(dupe)

    if dry_run:
        stats.created = len(redirects_to_create)
        stats.updated = len(to_unpublish)
        return stats

    with transaction.atomic():
        if redirects_to_create:
            ProductSlugRedirect.objects.bulk_create(redirects_to_create, ignore_conflicts=True)
            stats.created = len(redirects_to_create)
        if to_unpublish:
            for product in to_unpublish:
                product.is_published = False
            Product.objects.bulk_update(to_unpublish, ["is_published"])
            stats.updated = len(to_unpublish)

    return stats


def load_article_reparent_mapping(path: Path) -> list[tuple[int | None, str | None, str, str]]:
    """
    Load reparent mapping CSV.

    Supported columns (header row):
    - article_id, product_slug
    - article_slug, from_product_slug, to_product_slug
    """
    rows: list[tuple[int | None, str | None, str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = {name.strip().lower() for name in (reader.fieldnames or [])}
        for row in reader:
            if "article_id" in fieldnames and row.get("article_id"):
                article_id = int(row["article_id"])
                to_slug = (row.get("product_slug") or row.get("to_product_slug") or "").strip()
                if to_slug:
                    rows.append((article_id, None, "", to_slug))
                continue
            article_slug = (row.get("article_slug") or "").strip()
            from_slug = (row.get("from_product_slug") or row.get("from_slug") or "").strip()
            to_slug = (row.get("to_product_slug") or row.get("product_slug") or "").strip()
            if article_slug and to_slug:
                rows.append((None, article_slug, from_slug, to_slug))
    return rows


def reparent_product_articles(
    *,
    dry_run: bool = False,
    mapping_path: Path | None = None,
    auto_detect: bool = True,
) -> MaintenanceStats:
    """Move articles to the product that matches the model referenced in the headline."""
    stats = MaintenanceStats()
    products_by_slug = {
        (p.slug or "").strip(): p
        for p in Product.objects.filter(is_discontinued=False, is_published=True)
    }

    proposals: dict[int, Product] = {}

    if mapping_path and mapping_path.is_file():
        for article_id, article_slug, from_slug, to_slug in load_article_reparent_mapping(mapping_path):
            target = products_by_slug.get(to_slug)
            if not target:
                stats.skipped += 1
                continue
            if article_id is not None:
                article = ProductArticle.objects.filter(pk=article_id).select_related("product").first()
            else:
                qs = ProductArticle.objects.filter(slug=article_slug).select_related("product")
                if from_slug:
                    qs = qs.filter(product__slug=from_slug)
                article = qs.first()
            if not article:
                stats.skipped += 1
                continue
            proposals[article.id] = target

    if auto_detect:
        articles = ProductArticle.objects.filter(is_published=True).select_related("product")
        stats.scanned = articles.count()
        for article in articles:
            if article.id in proposals:
                continue
            model_key = extract_model_from_headline(article.headline, brand=article.product.brand)
            if not model_key:
                continue
            target = find_product_for_model(
                model_key,
                brand=article.product.brand or "Apple",
                product_type=article.product.product_type,
            )
            if not target or target.id == article.product_id:
                continue
            current_slug = (article.product.slug or "").strip()
            model_slug = slugify_seo(model_key)
            if model_slug and model_slug in current_slug:
                continue
            proposals[article.id] = target

    if dry_run:
        stats.updated = len(proposals)
        for article_id, target in list(proposals.items())[:40]:
            article = ProductArticle.objects.filter(pk=article_id).select_related("product").first()
            if article:
                stats.notes.append(
                    f"article id={article_id} {article.slug}: "
                    f"{article.product.slug} -> {target.slug}"
                )
        return stats

    with transaction.atomic():
        for article_id, target in proposals.items():
            article = ProductArticle.objects.filter(pk=article_id).first()
            if not article or article.product_id == target.id:
                stats.skipped += 1
                continue
            conflict = ProductArticle.objects.filter(product=target, slug=article.slug).exclude(pk=article_id).exists()
            if conflict:
                stats.skipped += 1
                stats.notes.append(f"skip article id={article_id}: slug collision on {target.slug}")
                continue
            article.product = target
            article.save(update_fields=["product"])
            stats.updated += 1

    return stats


def _article_body_hash(article: ProductArticle) -> str:
    payload = (article.headline or "").strip() + "\n" + (article.body or "").strip()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def deduplicate_product_articles(*, dry_run: bool = False) -> MaintenanceStats:
    """Remove cross-product duplicate articles, keeping the copy on the best-matching product."""
    stats = MaintenanceStats()
    articles = list(
        ProductArticle.objects.filter(is_published=True)
        .select_related("product")
        .order_by("-published_at", "id")
    )
    stats.scanned = len(articles)

    by_slug: dict[str, list[ProductArticle]] = defaultdict(list)
    by_hash: dict[str, list[ProductArticle]] = defaultdict(list)
    for article in articles:
        slug = (article.slug or "").strip()
        if slug:
            by_slug[slug].append(article)
        by_hash[_article_body_hash(article)].append(article)

    to_delete: list[ProductArticle] = []
    seen_ids: set[int] = set()

    def pick_keepers(group: list[ProductArticle]) -> ProductArticle:
        products = [article.product for article in group]
        canonical_product = pick_canonical_product(products)
        for article in group:
            model_key = extract_model_from_headline(article.headline, brand=article.product.brand)
            if model_key:
                matched = find_product_for_model(
                    model_key,
                    brand=article.product.brand or "",
                    product_type=article.product.product_type,
                )
                if matched:
                    canonical_product = matched
                    break
        for article in group:
            if article.product_id == canonical_product.id:
                return article
        return group[0]

    for slug, group in by_slug.items():
        if len(group) < 2:
            continue
        product_ids = {article.product_id for article in group}
        if len(product_ids) < 2:
            continue
        keeper = pick_keepers(group)
        for article in group:
            if article.id == keeper.id or article.id in seen_ids:
                continue
            to_delete.append(article)
            seen_ids.add(article.id)
            stats.notes.append(
                f"duplicate slug={slug}: drop id={article.id} on {article.product.slug}, "
                f"keep id={keeper.id} on {keeper.product.slug}"
            )

    for body_hash, group in by_hash.items():
        if len(group) < 2:
            continue
        product_ids = {article.product_id for article in group}
        if len(product_ids) < 2:
            continue
        keeper = pick_keepers(group)
        for article in group:
            if article.id == keeper.id or article.id in seen_ids:
                continue
            to_delete.append(article)
            seen_ids.add(article.id)
            stats.notes.append(
                f"duplicate body hash: drop id={article.id} on {article.product.slug}, "
                f"keep id={keeper.id} on {keeper.product.slug}"
            )

    if dry_run:
        stats.deleted = len(to_delete)
        return stats

    with transaction.atomic():
        deleted_count, _ = ProductArticle.objects.filter(
            id__in=[article.id for article in to_delete]
        ).delete()
        stats.deleted = deleted_count

    return stats


def fix_apostrophe_article_slugs(*, dry_run: bool = False) -> MaintenanceStats:
    """Normalize apostrophe-bug article slugs and record legacy redirects."""
    stats = MaintenanceStats()
    articles = list(ProductArticle.objects.filter(is_published=True).select_related("product"))
    stats.scanned = len(articles)

    redirects_to_create: list[ProductArticleSlugRedirect] = []
    slug_updates: list[ProductArticle] = []

    existing_pairs = {
        (row["product_id"], row["old_slug"])
        for row in ProductArticleSlugRedirect.objects.values("product_id", "old_slug")
    }

    for article in articles:
        current_slug = (article.slug or "").strip()
        if not current_slug:
            continue
        canonical = slugify_seo(article.headline) if article.headline else current_slug
        variants = apostrophe_bug_slug_variants(current_slug)
        if canonical and canonical != current_slug and canonical in variants:
            target_slug = canonical
        elif canonical == current_slug:
            continue
        else:
            target_slug = canonical if canonical else current_slug

        if target_slug == current_slug:
            continue

        conflict = (
            ProductArticle.objects.filter(product_id=article.product_id, slug=target_slug)
            .exclude(pk=article.pk)
            .exists()
        )
        if conflict:
            stats.skipped += 1
            stats.notes.append(
                f"skip article id={article.id}: target slug {target_slug} already exists"
            )
            continue

        pair = (article.product_id, current_slug)
        if pair not in existing_pairs:
            redirects_to_create.append(
                ProductArticleSlugRedirect(
                    product_id=article.product_id,
                    old_slug=current_slug,
                    article_id=article.id,
                )
            )
            existing_pairs.add(pair)

        article.slug = target_slug
        slug_updates.append(article)
        stats.notes.append(f"article id={article.id}: {current_slug} -> {target_slug}")

    if dry_run:
        stats.created = len(redirects_to_create)
        stats.updated = len(slug_updates)
        return stats

    with transaction.atomic():
        if redirects_to_create:
            ProductArticleSlugRedirect.objects.bulk_create(redirects_to_create, ignore_conflicts=True)
            stats.created = len(redirects_to_create)
        if slug_updates:
            ProductArticle.objects.bulk_update(slug_updates, ["slug"])
            stats.updated = len(slug_updates)

    return stats
