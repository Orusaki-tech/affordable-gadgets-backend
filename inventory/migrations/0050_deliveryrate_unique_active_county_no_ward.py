from django.db import migrations, models
from django.db.models import Count, Q


def dedupe_active_county_level_delivery_rates(apps, schema_editor):
    DeliveryRate = apps.get_model("inventory", "DeliveryRate")
    dup_counties = (
        DeliveryRate.objects.filter(is_active=True)
        .filter(Q(ward__isnull=True) | Q(ward=""))
        .values("county")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )
    for row in dup_counties:
        county = row["county"]
        rates = (
            DeliveryRate.objects.filter(is_active=True, county=county)
            .filter(Q(ward__isnull=True) | Q(ward=""))
            .order_by("id")
        )
        keep = rates.first()
        if keep is None:
            continue
        rates.exclude(pk=keep.pk).update(is_active=False)


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0049_financingprovider_financingoffer"),
    ]

    operations = [
        migrations.RunPython(dedupe_active_county_level_delivery_rates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="deliveryrate",
            constraint=models.UniqueConstraint(
                condition=Q(is_active=True) & (Q(ward__isnull=True) | Q(ward="")),
                fields=("county",),
                name="uniq_delivery_active_county_no_ward",
            ),
        ),
    ]
