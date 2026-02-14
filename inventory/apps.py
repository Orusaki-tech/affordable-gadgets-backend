import os
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'inventory'

    def ready(self):
        """Import signals when app is ready."""
        import inventory.signals  # noqa
        self._ensure_silk_profiles_dir()

    @staticmethod
    def _ensure_silk_profiles_dir():
        """Ensure Silk profiler output directory exists (e.g. on Render)."""
        from django.conf import settings
        if not getattr(settings, 'SILKY_ENABLED', False):
            return
        path = getattr(settings, 'SILKY_PYTHON_PROFILER_RESULT_PATH', None)
        if path:
            os.makedirs(path, exist_ok=True)