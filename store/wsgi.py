"""
WSGI config for store project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from inventory.observability import clear_prometheus_multiproc_dir

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "store.settings")

# Clear Prometheus multiproc directory in the master WSGI process
# before Gunicorn forks workers. This prevents stale metrics.
clear_prometheus_multiproc_dir()

application = get_wsgi_application()
