import json
from pathlib import Path

import pytest
from model_bakery import baker

from inventory.management.commands.reparent_articles_from_fixtures import (
    _load_fixture_rows,
    _resolve_target_product,
)
from inventory.models import Product, ProductArticle


@pytest.mark.django_db
def test_reparent_from_fixtures_moves_article_to_exact_product_name(tmp_path, monkeypatch):
    import inventory.management.commands.reparent_articles_from_fixtures as mod

    fixture_dir = tmp_path / "batches" / "test-batch"
    fixture_dir.mkdir(parents=True)
    fixture = {
        "product_slug": "iphone-15-pro",
        "product_name": "iPhone 15 Pro",
        "headline": "iPhone 15 Pro Review: titanium flagship",
        "is_published": True,
    }
    (fixture_dir / "001-iphone-15-pro.json").write_text(json.dumps(fixture), encoding="utf-8")
    monkeypatch.setattr(mod, "BATCHES_DIR", tmp_path / "batches")

    wrong_parent = baker.make(
        Product,
        slug="apple-iphone-13-sim",
        product_name="iPhone 13 SIM",
        brand="Apple",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    right_parent = baker.make(
        Product,
        slug="apple-iphone-15-pro",
        product_name="iPhone 15 Pro",
        brand="Apple",
        model_series="iPhone 15 Pro",
        product_type=Product.ProductType.PHONE,
        is_published=True,
        is_discontinued=False,
    )
    article = ProductArticle.objects.create(
        product=wrong_parent,
        slug="iphone-15-pro-review",
        headline=fixture["headline"],
        is_published=True,
    )

    from django.core.management import call_command

    call_command("reparent_articles_from_fixtures")

    article.refresh_from_db()
    assert article.product_id == right_parent.id
    assert _resolve_target_product("iPhone 15 Pro", "iphone-15-pro") == right_parent


def test_load_fixture_rows_reads_blog_batches():
    rows = _load_fixture_rows()
    assert len(rows) >= 300
    iphone_rows = [row for row in rows if row["product_name"] == "iPhone 13 Pro"]
    assert iphone_rows
    assert iphone_rows[0]["product_slug"] == "iphone-13-pro"
