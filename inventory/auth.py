"""
Custom DRF authentication classes that propagate the authenticated user
to the underlying Django HttpRequest so middleware can see it.
"""

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
