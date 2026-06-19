from django.test import SimpleTestCase

from inventory.catalog_matching import (
    name_similarity,
    should_skip_article_copy,
)


class CatalogMatchingTests(SimpleTestCase):
    def test_macbook_inch_variants_match(self):
        left = 'MacBook Air M4 13"'
        right = "MacBook Air M4 13 inch 256GB 16GB RAM"
        self.assertGreaterEqual(name_similarity(left, right), 0.5)

    def test_ipad_gen_cellular_matches_legacy_name(self):
        left = "iPad 11th Gen Cellular"
        right = "iPad 11th gen"
        self.assertGreaterEqual(name_similarity(left, right), 0.5)

    def test_unrelated_products_score_low(self):
        self.assertLess(
            name_similarity("Galaxy A07", "MacBook Air M4 13 inch"),
            0.2,
        )

    def test_samsung_galaxy_prefix_variants_match(self):
        self.assertGreaterEqual(name_similarity("Galaxy A07", "Samsung Galaxy A07"), 0.65)

    def test_skip_marketing_article_copy_to_stock_sku(self):
        self.assertTrue(
            should_skip_article_copy("iPhone Air", "iPhone 17 Air E-SIM Blue/Black")
        )
        self.assertTrue(should_skip_article_copy("iPhone 17e", "iPhone 17E SIM"))
        self.assertFalse(
            should_skip_article_copy("iPad 11th gen", "iPad 11th Gen Cellular")
        )
