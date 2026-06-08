import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def verify_supabase_token(access_token: str) -> dict | None:
    """
    Verify a Supabase JWT by calling Supabase's /auth/v1/user endpoint.
    Returns user data dict on success, None on failure.
    """
    if not settings.SUPABASE_URL:
        logger.error("SUPABASE_URL not configured")
        return None

    try:
        resp = requests.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": settings.SUPABASE_ANON_KEY,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            logger.info("Supabase token verified for user: %s", data.get("email", "unknown"))
            return data
        else:
            logger.warning(
                "Supabase token verification failed: %s %s",
                resp.status_code,
                resp.text[:200],
            )
            return None
    except requests.RequestException as e:
        logger.error("Supabase token verification error: %s", e)
        return None
