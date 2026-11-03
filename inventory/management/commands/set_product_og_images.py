import logging

from cloudinary import uploader
from django.core.management.base import BaseCommand

from inventory.models import Product, ProductImage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set og_image on each product from its primary product image"

    def handle(self, **options):
        qs = Product.objects.filter(is_published=True, og_image__isnull=True)
        total = qs.count()
        done = 0
        errors = 0

        for product in qs.iterator(chunk_size=50):
            primary = ProductImage.objects.filter(
                product=product, is_primary=True
            ).first()
            if not primary:
                primary = ProductImage.objects.filter(product=product).first()
            if not primary or not primary.image:
                errors += 1
                continue

            try:
                result = uploader.upload(
                    primary.image.url,
                    folder="og_images",
                    public_id=f"og_{product.id}_{product.slug or product.id}",
                    overwrite=True,
                )
                product.og_image.name = result["public_id"]
                product.save(update_fields=["og_image"])
                done += 1
                if done % 50 == 0:
                    logger.info(f"  {done}/{total} products updated")
            except Exception as e:
                errors += 1
                logger.warning(f"  FAIL {product.product_name} (id={product.id}): {e}")

        logger.info(f"Done: {done} updated, {errors} errors / {total}")
