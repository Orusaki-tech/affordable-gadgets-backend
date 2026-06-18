# Generated manually — migrate ProductArticle from OneToOne PK to FK with id + slug.

import django.db.models.deletion
from django.db import migrations, models
from django.utils.text import slugify


def _column_names(cursor, table):
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = %s
        """,
        [table],
    )
    return {row[0] for row in cursor.fetchall()}


def migrate_productarticle_schema(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                """
                SELECT 1 FROM pg_constraint
                WHERE conrelid = 'inventory_productarticle'::regclass AND contype = 'p'
                """
            )
            pk_col = None
            if cursor.fetchone():
                cursor.execute(
                    """
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = 'inventory_productarticle'::regclass AND i.indisprimary
                    LIMIT 1
                    """
                )
                row = cursor.fetchone()
                pk_col = row[0] if row else None

            cols = _column_names(cursor, "inventory_productarticle")
            if pk_col == "id" and "slug" in cols and "is_primary" in cols:
                return

            if "slug" not in cols:
                cursor.execute(
                    "ALTER TABLE inventory_productarticle ADD COLUMN slug VARCHAR(255) DEFAULT 'legacy' NOT NULL"
                )
            if "is_primary" not in cols:
                cursor.execute(
                    "ALTER TABLE inventory_productarticle ADD COLUMN is_primary BOOLEAN DEFAULT FALSE NOT NULL"
                )
            if "id" not in cols:
                cursor.execute("ALTER TABLE inventory_productarticle ADD COLUMN id BIGINT")

            ProductArticle = apps.get_model("inventory", "ProductArticle")
            used = set()
            for article in ProductArticle.objects.all().order_by("product_id"):
                product_id = article.product_id
                if not article.id:
                    article.id = product_id
                base = slugify(article.headline) or f"article-{product_id}"
                slug = article.slug if article.slug and article.slug != "legacy" else base
                counter = 1
                while (product_id, slug) in used:
                    slug = f"{base}-{counter}"
                    counter += 1
                used.add((product_id, slug))
                article.slug = slug
                article.is_primary = True
                article.save(update_fields=["id", "slug", "is_primary"])

            if pk_col != "id":
                cursor.execute(
                    """
                    ALTER TABLE inventory_articleimage
                    DROP CONSTRAINT IF EXISTS inventory_articleima_article_id_cc86c0c3_fk_inventory;
                    """
                )
                cursor.execute(
                    """
                    ALTER TABLE inventory_articleimage
                    DROP CONSTRAINT IF EXISTS inventory_articleima_article_id_fk;
                    """
                )
                cursor.execute(
                    "ALTER TABLE inventory_productarticle DROP CONSTRAINT IF EXISTS inventory_productarticle_pkey CASCADE;"
                )
                cursor.execute("ALTER TABLE inventory_productarticle ADD PRIMARY KEY (id);")
                cursor.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS unique_product_article_slug "
                    "ON inventory_productarticle (product_id, slug);"
                )
                cursor.execute(
                    """
                    ALTER TABLE inventory_articleimage
                    ADD CONSTRAINT inventory_articleima_article_id_fk
                    FOREIGN KEY (article_id) REFERENCES inventory_productarticle(id)
                    DEFERRABLE INITIALLY DEFERRED;
                    """
                )

        elif vendor == "sqlite":
            cols = _column_names(cursor, "inventory_productarticle")
            if "id" in cols and "slug" in cols:
                cursor.execute("PRAGMA table_info(inventory_productarticle)")
                info = cursor.fetchall()
                id_col = next((row for row in info if row[1] == "id"), None)
                if id_col and id_col[5] == 1:
                    cursor.execute("PRAGMA index_list(inventory_productarticle)")
                    indices = {row[1] for row in cursor.fetchall()}
                    if "unique_product_article_slug" in indices:
                        return

            if "slug" not in cols:
                cursor.execute(
                    "ALTER TABLE inventory_productarticle ADD COLUMN slug VARCHAR(255) NOT NULL DEFAULT 'legacy'"
                )
            if "is_primary" not in cols:
                cursor.execute(
                    "ALTER TABLE inventory_productarticle ADD COLUMN is_primary BOOL NOT NULL DEFAULT 0"
                )
            if "id" not in cols:
                cursor.execute("ALTER TABLE inventory_productarticle ADD COLUMN id INTEGER")

            ProductArticle = apps.get_model("inventory", "ProductArticle")
            used = set()
            for article in ProductArticle.objects.all().order_by("product_id"):
                product_id = article.product_id
                if not article.id:
                    article.id = product_id
                base = slugify(article.headline) or f"article-{product_id}"
                slug = article.slug if article.slug and article.slug != "legacy" else base
                counter = 1
                while (product_id, slug) in used:
                    slug = f"{base}-{counter}"
                    counter += 1
                used.add((product_id, slug))
                article.slug = slug
                article.is_primary = True
                article.save(update_fields=["id", "slug", "is_primary"])

            cursor.execute("PRAGMA foreign_keys=OFF")
            cursor.execute(
                """
                CREATE TABLE inventory_productarticle_new (
                    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                    slug VARCHAR(255) NOT NULL,
                    is_primary BOOL NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    thumbnail_image VARCHAR(100) NULL,
                    headline VARCHAR(255) NOT NULL,
                    seo_title VARCHAR(60) NOT NULL,
                    seo_description TEXT NOT NULL,
                    body TEXT NOT NULL,
                    is_published BOOL NOT NULL,
                    published_at DATETIME NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    product_id BIGINT NOT NULL REFERENCES inventory_product(id)
                );
                """
            )
            cursor.execute(
                """
                INSERT INTO inventory_productarticle_new (
                    id, slug, is_primary, category, thumbnail_image, headline,
                    seo_title, seo_description, body, is_published, published_at,
                    created_at, updated_at, product_id
                )
                SELECT
                    id, slug, is_primary, category, thumbnail_image, headline,
                    seo_title, seo_description, body, is_published, published_at,
                    created_at, updated_at, product_id
                FROM inventory_productarticle;
                """
            )
            cursor.execute("DROP TABLE inventory_productarticle;")
            cursor.execute(
                "ALTER TABLE inventory_productarticle_new RENAME TO inventory_productarticle;"
            )
            cursor.execute(
                "CREATE INDEX inventory_productarticle_product_id_idx ON inventory_productarticle (product_id);"
            )
            cursor.execute(
                "CREATE INDEX inventory_p_slug_0a8f2d_idx ON inventory_productarticle (slug);"
            )
            cursor.execute(
                "CREATE UNIQUE INDEX unique_product_article_slug ON inventory_productarticle (product_id, slug);"
            )
            cursor.execute("PRAGMA foreign_keys=ON")


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0065_backfill_product_release_dates"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(migrate_productarticle_schema, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name="productarticle",
                    name="slug",
                    field=models.SlugField(default="legacy", max_length=255),
                    preserve_default=False,
                ),
                migrations.AddField(
                    model_name="productarticle",
                    name="is_primary",
                    field=models.BooleanField(
                        default=False,
                        help_text="Default article for legacy /products/{slug}/blog URLs",
                    ),
                ),
                migrations.AddField(
                    model_name="productarticle",
                    name="id",
                    field=models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                migrations.AlterField(
                    model_name="productarticle",
                    name="product",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="articles",
                        to="inventory.product",
                    ),
                ),
                migrations.AlterField(
                    model_name="productarticle",
                    name="category",
                    field=models.CharField(
                        choices=[
                            ("buying_guide", "Buying Guide"),
                            ("history_guide", "History Guide"),
                            ("informational_guide", "Informational Guide"),
                            ("tech_tip", "Tech Tip"),
                            ("news", "News"),
                            ("general", "General"),
                        ],
                        default="buying_guide",
                        max_length=50,
                    ),
                ),
                migrations.AlterField(
                    model_name="productarticle",
                    name="slug",
                    field=models.SlugField(
                        help_text="URL segment under /products/{product-slug}/blog/{slug}/",
                        max_length=255,
                    ),
                ),
                migrations.AlterModelOptions(
                    name="productarticle",
                    options={"ordering": ["-is_primary", "-published_at", "id"]},
                ),
                migrations.AddIndex(
                    model_name="productarticle",
                    index=models.Index(fields=["slug"], name="inventory_p_slug_0a8f2d_idx"),
                ),
                migrations.AddConstraint(
                    model_name="productarticle",
                    constraint=models.UniqueConstraint(
                        fields=("product", "slug"),
                        name="unique_product_article_slug",
                    ),
                ),
            ],
        ),
    ]
