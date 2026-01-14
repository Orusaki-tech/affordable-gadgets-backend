"""
URL Resolution Debugging Middleware
Logs which URL pattern matches for receipt requests
"""
import json
import time
import logging

logger = logging.getLogger(__name__)

class URLResolutionDebugMiddleware:
    """
    Middleware to debug URL resolution for receipt endpoint.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # #region agent log
        log_path = '/Users/shwariphones/Desktop/shwari-django/affordable-gadgets-backend/.cursor/debug.log'
        if 'receipt' in request.path:
            try:
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'inventory/middleware.py:__call__',
                        'message': 'Receipt request detected in middleware',
                        'data': {
                            'path': request.path,
                            'method': request.method,
                            'full_path': request.get_full_path(),
                        },
                        'timestamp': int(time.time() * 1000)
                    }) + '\n')
            except Exception as e:
                logger.error(f"Failed to write debug log: {e}")
        # #endregion
        
        response = self.get_response(request)
        
        # #region agent log
        if 'receipt' in request.path:
            try:
                resolver_match = getattr(request, 'resolver_match', None)
                with open(log_path, 'a') as f:
                    f.write(json.dumps({
                        'sessionId': 'debug-session',
                        'runId': 'run1',
                        'hypothesisId': 'A',
                        'location': 'inventory/middleware.py:__call__',
                        'message': 'After URL resolution',
                        'data': {
                            'path': request.path,
                            'resolver_match_exists': resolver_match is not None,
                            'resolver_route': resolver_match.route if resolver_match else None,
                            'resolver_url_name': resolver_match.url_name if resolver_match else None,
                            'resolver_kwargs': dict(resolver_match.kwargs) if resolver_match else None,
                            'resolver_view': str(resolver_match.func) if resolver_match and hasattr(resolver_match, 'func') else None,
                            'response_status': response.status_code,
                        },
                        'timestamp': int(time.time() * 1000)
                    }) + '\n')
            except Exception as e:
                logger.error(f"Failed to write debug log: {e}")
        # #endregion
        
        return response
