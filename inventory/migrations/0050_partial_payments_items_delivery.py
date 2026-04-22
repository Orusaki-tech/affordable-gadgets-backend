from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0049_financingprovider_financingoffer"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="is_items_paid",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="is_delivery_paid",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="pesapalpayment",
            name="payment_purpose",
            field=models.CharField(
                choices=[
                    ("ITEMS_ONLY", "Items only"),
                    ("DELIVERY_ONLY", "Delivery only"),
                    ("BOTH", "Items + Delivery"),
                ],
                default="BOTH",
                help_text="What this payment covers (items, delivery, or both).",
                max_length=20,
            ),
        ),
    ]

