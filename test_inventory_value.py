import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings")
django.setup()

from inventory.observability import refresh_business_metrics, INVENTORY_VALUE
from inventory.models import Brand
import prometheus_client

print("Running refresh_business_metrics()...")
refresh_business_metrics()
print("Done.")

print("\n--- Prometheus Gauge Check ---")
print(prometheus_client.generate_latest(prometheus_client.REGISTRY).decode("utf-8"))
