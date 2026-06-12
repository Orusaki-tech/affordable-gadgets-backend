"""
Custom DRF authentication classes that propagate the authenticated user
to the underlying Django HttpRequest so middleware can see it.
"""

from rest_framework import exceptions
from rest_framework.authentication import TokenAuthentication


class TrackingTokenAuthentication(TokenAuthentication):
    """Extends TokenAuthentication to set the authenticated user on the
    underlying Django HttpRequest, making it visible to middleware that
    runs during the response phase (e.g. RequestTimingMiddleware)."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, token = result
            request._request.user = user
        return result


class OptionalTrackingTokenAuthentication(TrackingTokenAuthentication):
    """Token auth that allows anonymous access when the token is missing or invalid."""

    def authenticate(self, request):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Token "):
            return None
        try:
            return super().authenticate(request)
        except exceptions.AuthenticationFailed:
            return None
