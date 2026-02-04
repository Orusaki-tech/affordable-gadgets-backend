"""
Gmail API email backend using OAuth2 refresh tokens.
Sends Django EmailMessage objects via Gmail API.
"""
import base64
import logging
import random
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_httplib2 import AuthorizedHttp
import httplib2

logger = logging.getLogger(__name__)

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


class GmailApiEmailBackend(BaseEmailBackend):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.client_id = getattr(settings, "GMAIL_CLIENT_ID", "")
        self.client_secret = getattr(settings, "GMAIL_CLIENT_SECRET", "")
        self.refresh_token = getattr(settings, "GMAIL_REFRESH_TOKEN", "")
        self.sender = getattr(settings, "GMAIL_SENDER", "") or getattr(
            settings, "DEFAULT_FROM_EMAIL", ""
        )
        self.timeout = int(getattr(settings, "GMAIL_API_TIMEOUT", 10))
        self.max_retries = int(getattr(settings, "GMAIL_MAX_RETRIES", 3))
        self.retry_base_delay = float(getattr(settings, "GMAIL_RETRY_BASE_DELAY", 1.0))

        missing = [
            name
            for name, value in [
                ("GMAIL_CLIENT_ID", self.client_id),
                ("GMAIL_CLIENT_SECRET", self.client_secret),
                ("GMAIL_REFRESH_TOKEN", self.refresh_token),
                ("GMAIL_SENDER", self.sender),
            ]
            if not value
        ]
        if missing:
            raise ImproperlyConfigured(
                f"Missing Gmail API settings: {', '.join(missing)}"
            )

        self._service = None

    def _build_service(self):
        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=[GMAIL_SEND_SCOPE],
        )
        http = httplib2.Http(timeout=self.timeout)
        authed_http = AuthorizedHttp(credentials, http=http)
        return build("gmail", "v1", http=authed_http, cache_discovery=False)

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        sent_count = 0
        for message in email_messages:
            if not (message.to or message.cc or message.bcc):
                continue
            if not message.from_email:
                message.from_email = self.sender

            try:
                raw_message = base64.urlsafe_b64encode(
                    message.message().as_bytes()
                ).decode("utf-8")
                body = {"raw": raw_message}
                if self._send_with_retry(body):
                    sent_count += 1
            except Exception:
                logger.exception("Failed to send Gmail API email.")
                if not self.fail_silently:
                    raise

        return sent_count

    def _send_with_retry(self, body):
        attempt = 0
        while True:
            try:
                self.service.users().messages().send(userId="me", body=body).execute(
                    num_retries=0
                )
                return True
            except HttpError as exc:
                status = getattr(exc.resp, "status", None)
                if status in (429, 500, 502, 503, 504):
                    attempt += 1
                    if attempt > self.max_retries:
                        logger.error("Gmail API send failed after retries: %s", exc)
                        if not self.fail_silently:
                            raise
                        return False
                    delay = self.retry_base_delay * (2 ** (attempt - 1))
                    delay += random.uniform(0, delay * 0.1)
                    time.sleep(delay)
                    continue
                logger.exception("Gmail API send failed.")
                if not self.fail_silently:
                    raise
                return False
