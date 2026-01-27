"""
Custom SMTP email backend with improved TLS certificate handling.
Uses certifi CA bundle when available and allows opt-in invalid certs for dev.
"""
import ssl
from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as DjangoEmailBackend
from django.utils.functional import cached_property


class EmailBackend(DjangoEmailBackend):
    @cached_property
    def ssl_context(self):
        """
        Build an SSL context with a CA bundle when possible.
        - If EMAIL_TLS_ALLOW_INVALID_CERTS is True, disable verification (dev only).
        - If EMAIL_SSL_CA_FILE is set, use it as the CA bundle.
        - Otherwise, fall back to certifi if installed, then system defaults.
        """
        if getattr(settings, "EMAIL_TLS_ALLOW_INVALID_CERTS", False):
            return ssl._create_unverified_context()

        ca_file = getattr(settings, "EMAIL_SSL_CA_FILE", None)
        if not ca_file:
            try:
                import certifi
                ca_file = certifi.where()
            except Exception:
                ca_file = None

        if ca_file:
            return ssl.create_default_context(cafile=ca_file)

        return ssl.create_default_context()
