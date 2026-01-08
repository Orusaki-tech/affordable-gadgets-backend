"""
Pesapal API 3.0 service with comprehensive failover and error handling.
Handles authentication, order submission, payment status queries, and IPN handling.
"""
import requests
import time
import logging
import json
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from typing import Dict, Optional, Tuple
from requests.exceptions import Timeout, ConnectionError, RequestException

logger = logging.getLogger(__name__)

class PesapalService:
    """Pesapal API 3.0 service with failover and retry logic."""
    
    def __init__(self):
        # #region agent log
        import json
        import os
        # Use PESAPAL_LOG_PATH from environment variable, fallback to /tmp/pesapal_debug.log
        log_path = getattr(settings, 'PESAPAL_LOG_PATH', '/tmp/pesapal_debug.log')
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'pesapal_service.py:__init__',
                    'message': 'PesapalService initialization start',
                    'data': {'timestamp': timezone.now().isoformat()},
                    'timestamp': int(timezone.now().timestamp() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[DEBUG] Failed to write log: {e}")
        # #endregion
        
        self.consumer_key = settings.PESAPAL_CONSUMER_KEY
        self.consumer_secret = settings.PESAPAL_CONSUMER_SECRET
        
        # #region agent log
        try:
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'A',
                    'location': 'pesapal_service.py:__init__',
                    'message': 'Credentials loaded from settings',
                    'data': {
                        'consumer_key_present': bool(self.consumer_key),
                        'consumer_key_length': len(self.consumer_key) if self.consumer_key else 0,
                        'consumer_key_first_10': self.consumer_key[:10] if self.consumer_key else None,
                        'consumer_key_full': str(self.consumer_key) if self.consumer_key else None,
                        'consumer_secret_present': bool(self.consumer_secret),
                        'consumer_secret_length': len(self.consumer_secret) if self.consumer_secret else 0,
                        'raw_key_from_settings': str(settings.PESAPAL_CONSUMER_KEY)[:20] if hasattr(settings, 'PESAPAL_CONSUMER_KEY') else None,
                        'raw_secret_from_settings': str(settings.PESAPAL_CONSUMER_SECRET)[:20] if hasattr(settings, 'PESAPAL_CONSUMER_SECRET') else None,
                    },
                    'timestamp': int(timezone.now().timestamp() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[DEBUG] Failed to write log: {e}")
        # #endregion
        
        self.environment = getattr(settings, 'PESAPAL_ENVIRONMENT', 'production')
        self.timeout = getattr(settings, 'PESAPAL_API_TIMEOUT', 30)
        self.max_retries = getattr(settings, 'PESAPAL_MAX_RETRIES', 3)
        self.retry_delay = getattr(settings, 'PESAPAL_RETRY_DELAY', 2)
        
        # Production API endpoint (as shown in your Postman test)
        self.base_url = 'https://pay.pesapal.com/v3'
        
        # Failover endpoints (if primary fails)
        self.failover_urls = []
        
        self._access_token = None
        self._token_expires_at = None
        print("[PESAPAL] Initializing PesapalService...")
        print(f"[PESAPAL] Service initialized - Base URL: {self.base_url}, Environment: {self.environment}")
        print(f"[PESAPAL] Consumer Key loaded: {self.consumer_key[:15] if self.consumer_key else 'None'}... (length: {len(self.consumer_key) if self.consumer_key else 0})")
        print(f"[PESAPAL] Consumer Secret loaded: {'*' * 15}... (length: {len(self.consumer_secret) if self.consumer_secret else 0})")
    
    def _make_request_with_failover(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Tuple[Optional[requests.Response], Optional[str]]:
        """Make HTTP request with failover support. Returns (response, error_message)."""
        print(f"\n[PESAPAL] ========== API REQUEST START ==========")
        print(f"[PESAPAL] Method: {method.upper()}")
        print(f"[PESAPAL] Endpoint: {endpoint}")
        print(f"[PESAPAL] Retry Count: {retry_count}")
        
        # Prepare headers for logging (hide sensitive data)
        safe_headers = {}
        if headers:
            for k, v in headers.items():
                if k.lower() == 'authorization':
                    safe_headers[k] = f"{v[:20]}..." if v else None
                else:
                    safe_headers[k] = v
        print(f"[PESAPAL] Headers: {json.dumps(safe_headers, indent=2)}")
        
        # Prepare data for logging (hide sensitive data)
        safe_data = {}
        if data:
            for k, v in data.items():
                if 'secret' in k.lower() or 'password' in k.lower():
                    safe_data[k] = "***HIDDEN***"
                else:
                    safe_data[k] = v
        print(f"[PESAPAL] Request Data: {json.dumps(safe_data, indent=2)}")
        
        urls_to_try = [self.base_url] + self.failover_urls
        
        for base_url in urls_to_try:
            url = f"{base_url}{endpoint}"
            print(f"[PESAPAL] Attempting request to: {url}")
            
            try:
                # #region agent log
                # Use PESAPAL_LOG_PATH from environment variable, fallback to /tmp/pesapal_debug.log
                log_path = getattr(settings, 'PESAPAL_LOG_PATH', '/tmp/pesapal_debug.log')
                if method.upper() == 'POST':
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'E',
                                'location': 'pesapal_service.py:_make_request_with_failover',
                                'message': 'Making HTTP POST request to Pesapal',
                                'data': {
                                    'url': url,
                                    'has_data': bool(data),
                                    'data_keys': list(data.keys()) if data else [],
                                    'consumer_key_in_data': 'consumer_key' in (data or {}),
                                    'consumer_secret_in_data': 'consumer_secret' in (data or {}),
                                    'headers': {k: v[:50] + '...' if len(str(v)) > 50 else v for k, v in (headers or {}).items()},
                                },
                                'timestamp': int(timezone.now().timestamp() * 1000)
                            }) + '\n')
                    except: pass
                # #endregion
                
                if method.upper() == 'POST':
                    print(f"[PESAPAL] Making POST request...")
                    # #region agent log
                    try:
                        with open(log_path, 'a') as f:
                            f.write(json.dumps({
                                'sessionId': 'debug-session',
                                'runId': 'run1',
                                'hypothesisId': 'E',
                                'location': 'pesapal_service.py:_make_request_with_failover',
                                'message': 'About to make POST request',
                                'data': {
                                    'url': url,
                                    'data_type': type(data).__name__,
                                    'data_is_none': data is None,
                                    'data_keys': list(data.keys()) if data and isinstance(data, dict) else None,
                                    'consumer_key_in_data': data.get('consumer_key') if data and isinstance(data, dict) else None,
                                    'consumer_key_is_none': data.get('consumer_key') is None if data and isinstance(data, dict) else None,
                                    'consumer_key_length': len(data.get('consumer_key', '')) if data and isinstance(data, dict) and data.get('consumer_key') else 0,
                                    'consumer_secret_in_data': '***' if data and isinstance(data, dict) and data.get('consumer_secret') else None,
                                    'consumer_secret_is_none': data.get('consumer_secret') is None if data and isinstance(data, dict) else None,
                                    'headers': dict(headers) if headers else None,
                                },
                                'timestamp': int(timezone.now().timestamp() * 1000)
                            }) + '\n')
                    except Exception as e:
                        print(f"[DEBUG] Log write error: {e}")
                    # #endregion
                    response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
                elif method.upper() == 'GET':
                    print(f"[PESAPAL] Making GET request...")
                    response = requests.get(url, params=data, headers=headers, timeout=self.timeout)
                else:
                    print(f"[PESAPAL] ERROR: Unsupported HTTP method: {method}")
                    return None, f"Unsupported HTTP method: {method}"
                
                print(f"[PESAPAL] Response Status Code: {response.status_code}")
                print(f"[PESAPAL] Response Headers: {dict(response.headers)}")
                
                # #region agent log
                try:
                    response_text_preview = response.text[:1000] if hasattr(response, 'text') else None
                    response_json = None
                    try:
                        response_json = response.json() if hasattr(response, 'json') else None
                    except:
                        pass
                    with open(log_path, 'a') as f:
                        f.write(json.dumps({
                            'sessionId': 'debug-session',
                            'runId': 'run1',
                            'hypothesisId': 'F',
                            'location': 'pesapal_service.py:_make_request_with_failover',
                            'message': 'HTTP response received from Pesapal',
                            'data': {
                                'status_code': response.status_code,
                                'response_ok': response.ok,
                                'response_text_full': response_text_preview,
                                'response_json': response_json,
                                'content_type': response.headers.get('Content-Type'),
                                'error_in_response': response_json.get('error') if response_json and isinstance(response_json, dict) else None,
                            },
                            'timestamp': int(timezone.now().timestamp() * 1000)
                        }) + '\n')
                except Exception as e:
                    print(f"[DEBUG] Log write error: {e}")
                # #endregion
                
                if response.status_code in [200, 201]:
                    try:
                        response_json = response.json()
                        print(f"[PESAPAL] SUCCESS - Response Body: {json.dumps(response_json, indent=2)}")
                    except:
                        print(f"[PESAPAL] SUCCESS - Response Text (first 500 chars): {response.text[:500]}")
                    print(f"[PESAPAL] ========== API REQUEST SUCCESS ==========\n")
                    return response, None
                
                # Try to extract error message from response
                error_message = f"HTTP {response.status_code}"
                try:
                    error_data = response.json()
                    print(f"[PESAPAL] ERROR - Full Response JSON: {json.dumps(error_data, indent=2)}")
                    logger.error(f"Pesapal API error response: {error_data}")
                    # CRITICAL: Check for "Authentication credentials were not provided" specifically
                    error_str = json.dumps(error_data)
                    if 'Authentication credentials were not provided' in error_str or 'credentials were not provided' in error_str.lower():
                        print(f"[PESAPAL] CRITICAL: Pesapal says credentials not provided!")
                        print(f"[PESAPAL] Request data that was sent: consumer_key present={bool(data and data.get('consumer_key'))}, consumer_secret present={bool(data and data.get('consumer_secret'))}")
                        if data:
                            print(f"[PESAPAL] Data keys: {list(data.keys())}")
                            print(f"[PESAPAL] Consumer key type: {type(data.get('consumer_key'))}, length: {len(str(data.get('consumer_key', '')))}")
                    if isinstance(error_data, dict):
                        if 'error' in error_data:
                            error_obj = error_data['error']
                            if isinstance(error_obj, dict):
                                error_message = error_obj.get('message') or error_obj.get('error_type') or error_obj.get('error_description') or error_message
                            else:
                                error_message = str(error_obj)
                        elif 'message' in error_data:
                            error_message = error_data['message']
                        # Check for common error fields
                        for field in ['errorMessage', 'error_description', 'errorMessage', 'detail']:
                            if field in error_data:
                                error_message = error_data[field]
                                break
                except Exception as json_error:
                    error_message = response.text[:200] if response.text else error_message
                    logger.error(f"Could not parse error response as JSON: {json_error}. Response text: {response.text[:500]}")
                
                if response.status_code in [401, 403]:
                    print(f"[PESAPAL] AUTHENTICATION ERROR ({response.status_code}): {error_message}")
                    if retry_count < self.max_retries:
                        print(f"[PESAPAL] Retrying with fresh token... (retry {retry_count + 1}/{self.max_retries})")
                        logger.warning(f"Authentication error ({response.status_code}): {error_message}, retrying with fresh token...")
                        self._access_token = None
                        time.sleep(self.retry_delay)
                        continue
                    else:
                        # Return more detailed error message
                        detailed_error = f"Authentication failed ({response.status_code}): {error_message}"
                        print(f"[PESAPAL] ========== API REQUEST FAILED ==========")
                        print(f"[PESAPAL] ERROR: {detailed_error}")
                        print(f"[PESAPAL] ========================================\n")
                        logger.error(f"Pesapal authentication failed: {detailed_error}")
                        return None, detailed_error
                
                print(f"[PESAPAL] ========== API REQUEST FAILED ==========")
                print(f"[PESAPAL] URL: {url}")
                print(f"[PESAPAL] Status: {response.status_code}")
                print(f"[PESAPAL] Error: {error_message}")
                print(f"[PESAPAL] ========================================\n")
                logger.warning(f"Request to {url} failed with status {response.status_code}: {error_message}")
                return None, f"API request failed ({response.status_code}): {error_message}"
                
            except (Timeout, ConnectionError) as e:
                logger.warning(f"Network error connecting to {url}: {str(e)}")
                if base_url == urls_to_try[-1] and retry_count < self.max_retries:
                    time.sleep(self.retry_delay * (retry_count + 1))
                    return self._make_request_with_failover(method, endpoint, data, headers, retry_count + 1)
                continue
            except RequestException as e:
                logger.error(f"Request exception for {url}: {str(e)}")
                continue
        
        return None, "All endpoints failed. Please try again later."
    
    def get_access_token(self, force_refresh: bool = False) -> Optional[str]:
        """Get access token from Pesapal API with failover support."""
        print(f"\n[PESAPAL] ========== GET ACCESS TOKEN START ==========")
        print(f"[PESAPAL] Force Refresh: {force_refresh}")
        
        # Validate credentials first
        if not self.consumer_key or not self.consumer_secret:
            print(f"[PESAPAL] ERROR: Credentials not configured!")
            logger.error("Pesapal credentials not configured")
            return None
        
        if not force_refresh and self._access_token and self._token_expires_at:
            if timezone.now() < self._token_expires_at:
                print(f"[PESAPAL] Using cached token (expires at: {self._token_expires_at})")
                print(f"[PESAPAL] ========== GET ACCESS TOKEN SUCCESS (CACHED) ==========\n")
                return self._access_token
        
        endpoint = '/api/Auth/RequestToken'
        
        # CRITICAL CHECK: Verify credentials before creating data dict
        # Check for None, empty string, or whitespace-only
        consumer_key_valid = self.consumer_key and str(self.consumer_key).strip()
        consumer_secret_valid = self.consumer_secret and str(self.consumer_secret).strip()
        
        if not consumer_key_valid or not consumer_secret_valid:
            error_msg = f"CREDENTIALS INVALID: key_valid={bool(consumer_key_valid)}, secret_valid={bool(consumer_secret_valid)}, key_type={type(self.consumer_key).__name__}, secret_type={type(self.consumer_secret).__name__}"
            print(f"[PESAPAL] CRITICAL ERROR: {error_msg}")
            logger.error(error_msg)
            return None
        
        # Ensure we're using string values (strip any whitespace)
        data = {
            "consumer_key": str(self.consumer_key).strip(),
            "consumer_secret": str(self.consumer_secret).strip()
        }
        
        # Final verification
        if not data.get('consumer_key') or not data.get('consumer_secret'):
            error_msg = f"DATA DICT INVALID AFTER STRIPPING: key={bool(data.get('consumer_key'))}, secret={bool(data.get('consumer_secret'))}"
            print(f"[PESAPAL] CRITICAL ERROR: {error_msg}")
            logger.error(error_msg)
            return None
        
        # #region agent log
        import json
        import os
        # Use PESAPAL_LOG_PATH from environment variable, fallback to /tmp/pesapal_debug.log
        log_path = getattr(settings, 'PESAPAL_LOG_PATH', '/tmp/pesapal_debug.log')
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            with open(log_path, 'a') as f:
                f.write(json.dumps({
                    'sessionId': 'debug-session',
                    'runId': 'run1',
                    'hypothesisId': 'B',
                    'location': 'pesapal_service.py:get_access_token',
                    'message': 'Preparing token request data',
                    'data': {
                        'consumer_key_present': bool(data.get('consumer_key')),
                        'consumer_key_length': len(data.get('consumer_key', '')) if data.get('consumer_key') else 0,
                        'consumer_key_value': data.get('consumer_key', '')[:20] + '...' if data.get('consumer_key') else None,
                        'consumer_key_is_none': data.get('consumer_key') is None,
                        'consumer_key_is_empty': data.get('consumer_key') == '',
                        'consumer_secret_present': bool(data.get('consumer_secret')),
                        'consumer_secret_length': len(data.get('consumer_secret', '')) if data.get('consumer_secret') else 0,
                        'consumer_secret_is_none': data.get('consumer_secret') is None,
                        'consumer_secret_is_empty': data.get('consumer_secret') == '',
                        'endpoint': endpoint,
                        'base_url': self.base_url,
                        'data_dict_keys': list(data.keys()),
                    },
                    'timestamp': int(timezone.now().timestamp() * 1000)
                }) + '\n')
        except Exception as e:
            print(f"[DEBUG] Failed to write log: {e}")
        # #endregion
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print(f"[PESAPAL] Requesting new token from: {self.base_url}{endpoint}")
        print(f"[PESAPAL] Consumer Key: {self.consumer_key[:15]}... (length: {len(self.consumer_key)})")
        print(f"[PESAPAL] Consumer Secret: {'*' * 15}... (length: {len(self.consumer_secret)})")
        
        # Log request details for debugging (without exposing full secret)
        logger.debug(f"Requesting token from: {self.base_url}{endpoint}")
        logger.debug(f"Consumer Key: {self.consumer_key[:10]}... (length: {len(self.consumer_key)})")
        logger.debug(f"Consumer Secret: {'*' * 10}... (length: {len(self.consumer_secret)})")
        
        response, error = self._make_request_with_failover('POST', endpoint, data, headers)
        
        if error or not response:
            error_msg = error or 'No response from Pesapal API'
            print(f"[PESAPAL] ========== GET ACCESS TOKEN FAILED ==========")
            print(f"[PESAPAL] ERROR: {error_msg}")
            logger.error(f"Failed to get access token: {error_msg}")
            # If it's an authentication error, provide more context
            if 'Authentication' in error_msg or '401' in error_msg or '403' in error_msg:
                print(f"[PESAPAL] This usually means:")
                print(f"[PESAPAL]   1) Credentials are incorrect")
                print(f"[PESAPAL]   2) Credentials need activation in Pesapal dashboard")
                print(f"[PESAPAL]   3) Credentials are for a different environment")
                logger.error("This usually means: 1) Credentials are incorrect, 2) Credentials need activation in Pesapal dashboard, or 3) Credentials are for a different environment")
            print(f"[PESAPAL] =============================================\n")
            return None
        
        try:
            result = response.json()
            if not result:
                print(f"[PESAPAL] ERROR: Empty response from Pesapal API")
                logger.error("Empty response from Pesapal API")
                return None
            
            print(f"[PESAPAL] Response received: {json.dumps(result, indent=2)}")
            
            # Log full response for debugging (in debug mode)
            logger.debug(f"Pesapal API response: {result}")
            
            error_info = result.get('error')
            if error_info is not None:
                if isinstance(error_info, dict):
                    error_message = error_info.get('message') or error_info.get('error_type') or error_info.get('error_description') or 'Unknown error'
                else:
                    error_message = str(error_info)
                print(f"[PESAPAL] ========== GET ACCESS TOKEN FAILED ==========")
                print(f"[PESAPAL] API Error: {error_message}")
                print(f"[PESAPAL] Full Response: {json.dumps(result, indent=2)}")
                print(f"[PESAPAL] =============================================\n")
                logger.error(f"Pesapal API error: {error_message}")
                logger.error(f"Full error response: {result}")
                return None
            
            token = result.get('token')
            if not token:
                print(f"[PESAPAL] ========== GET ACCESS TOKEN FAILED ==========")
                print(f"[PESAPAL] ERROR: No token in response")
                print(f"[PESAPAL] Response: {json.dumps(result, indent=2)}")
                print(f"[PESAPAL] =============================================\n")
                logger.error(f"No token in Pesapal API response. Response was: {result}")
                return None
            
            self._access_token = token
            self._token_expires_at = timezone.now() + timedelta(hours=1)
            
            print(f"[PESAPAL] ========== GET ACCESS TOKEN SUCCESS ==========")
            print(f"[PESAPAL] Token obtained (first 20 chars): {token[:20]}...")
            print(f"[PESAPAL] Token expires at: {self._token_expires_at}")
            print(f"[PESAPAL] ===============================================\n")
            logger.info("Successfully obtained Pesapal access token")
            return token
            
        except ValueError as e:
            print(f"[PESAPAL] ========== GET ACCESS TOKEN FAILED ==========")
            print(f"[PESAPAL] ERROR: Invalid JSON response - {str(e)}")
            print(f"[PESAPAL] =============================================\n")
            logger.error(f"Invalid JSON response from Pesapal: {str(e)}")
            return None
        except Exception as e:
            print(f"[PESAPAL] ========== GET ACCESS TOKEN FAILED ==========")
            print(f"[PESAPAL] ERROR: Unexpected error - {str(e)}")
            print(f"[PESAPAL] =============================================\n")
            logger.error(f"Unexpected error getting access token: {str(e)}")
            return None
    
    def submit_order_request(self, order_data: Dict) -> Tuple[Optional[Dict], Optional[str]]:
        """Submit order request to Pesapal with failover support."""
        print(f"\n[PESAPAL] ========== SUBMIT ORDER REQUEST START ==========")
        print(f"[PESAPAL] Order Data: {json.dumps(order_data, indent=2)}")
        
        # Validate credentials first
        if not self.consumer_key or not self.consumer_secret:
            print(f"[PESAPAL] ERROR: Credentials not configured")
            return None, "Pesapal credentials not configured. Please check PESAPAL_CONSUMER_KEY and PESAPAL_CONSUMER_SECRET in settings."
        
        print(f"[PESAPAL] Getting access token...")
        token = self.get_access_token()
        if not token:
            print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
            print(f"[PESAPAL] ERROR: Failed to obtain access token")
            print(f"[PESAPAL] ================================================\n")
            return None, "Failed to obtain access token from Pesapal. Please verify your credentials are correct and active."
        
        endpoint = '/api/Transactions/SubmitOrderRequest'
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        print(f"[PESAPAL] Submitting order request to Pesapal...")
        response, error = self._make_request_with_failover('POST', endpoint, order_data, headers)
        
        if error:
            print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
            print(f"[PESAPAL] ERROR: {error}")
            print(f"[PESAPAL] ================================================\n")
            return None, error
        
        if not response:
            print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
            print(f"[PESAPAL] ERROR: No response from Pesapal API")
            print(f"[PESAPAL] ================================================\n")
            return None, "No response from Pesapal API"
        
        try:
            result = response.json()
            if not result:
                print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
                print(f"[PESAPAL] ERROR: Empty response from Pesapal API")
                print(f"[PESAPAL] ================================================\n")
                return None, "Empty response from Pesapal API"
            
            print(f"[PESAPAL] Response received: {json.dumps(result, indent=2)}")
            
            # Check for error in response
            error_info = result.get('error')
            if error_info is not None:
                if isinstance(error_info, dict):
                    error_message = error_info.get('message') or error_info.get('error_type') or error_info.get('error_description') or 'Unknown error'
                else:
                    error_message = str(error_info)
                print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
                print(f"[PESAPAL] API Error: {error_message}")
                print(f"[PESAPAL] ================================================\n")
                return None, f"Pesapal API error: {error_message}"
            
            # Check for error message at top level
            if 'message' in result and result.get('message') and 'error' in result.get('message', '').lower():
                print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
                print(f"[PESAPAL] API Error: {result['message']}")
                print(f"[PESAPAL] ================================================\n")
                return None, f"Pesapal API error: {result['message']}"
            
            order_tracking_id = result.get('order_tracking_id')
            redirect_url = result.get('redirect_url')
            print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST SUCCESS ==========")
            print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
            print(f"[PESAPAL] Redirect URL: {redirect_url}")
            print(f"[PESAPAL] =================================================\n")
            return result, None
            
        except ValueError as e:
            print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
            print(f"[PESAPAL] ERROR: Invalid JSON response - {str(e)}")
            print(f"[PESAPAL] ================================================\n")
            return None, f"Invalid JSON response: {str(e)}"
        except Exception as e:
            print(f"[PESAPAL] ========== SUBMIT ORDER REQUEST FAILED ==========")
            print(f"[PESAPAL] ERROR: Unexpected error - {str(e)}")
            print(f"[PESAPAL] ================================================\n")
            return None, f"Unexpected error: {str(e)}"
    
    def get_transaction_status(self, order_tracking_id: str) -> Tuple[Optional[Dict], Optional[str]]:
        """Get transaction status from Pesapal with failover support."""
        print(f"\n[PESAPAL] ========== GET TRANSACTION STATUS START ==========")
        print(f"[PESAPAL] Order Tracking ID: {order_tracking_id}")
        
        print(f"[PESAPAL] Getting access token...")
        token = self.get_access_token()
        if not token:
            print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
            print(f"[PESAPAL] ERROR: Failed to obtain access token")
            print(f"[PESAPAL] ===================================================\n")
            return None, "Failed to obtain access token"
        
        endpoint = f'/api/Transactions/GetTransactionStatus?orderTrackingId={order_tracking_id}'
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        print(f"[PESAPAL] Requesting transaction status from Pesapal...")
        response, error = self._make_request_with_failover('GET', endpoint, None, headers)
        
        if error:
            print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
            print(f"[PESAPAL] ERROR: {error}")
            print(f"[PESAPAL] ===================================================\n")
            return None, error
        
        if not response:
            print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
            print(f"[PESAPAL] ERROR: No response from Pesapal API")
            print(f"[PESAPAL] ===================================================\n")
            return None, "No response from Pesapal API"
        
        try:
            result = response.json()
            if not result:
                print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
                print(f"[PESAPAL] ERROR: Empty response from Pesapal API")
                print(f"[PESAPAL] ===================================================\n")
                return None, "Empty response from Pesapal API"
            
            print(f"[PESAPAL] Response received: {json.dumps(result, indent=2)}")
            
            # Check for error in response
            error_info = result.get('error')
            if error_info is not None:
                if isinstance(error_info, dict):
                    error_message = error_info.get('message') or error_info.get('error_type') or error_info.get('error_description') or 'Unknown error'
                else:
                    error_message = str(error_info)
                print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
                print(f"[PESAPAL] API Error: {error_message}")
                print(f"[PESAPAL] ===================================================\n")
                return None, f"Pesapal API error: {error_message}"
            
            # Check for error message at top level
            if 'message' in result and result.get('message') and 'error' in result.get('message', '').lower():
                print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
                print(f"[PESAPAL] API Error: {result['message']}")
                print(f"[PESAPAL] ===================================================\n")
                return None, f"Pesapal API error: {result['message']}"
            
            print(f"[PESAPAL] ========== GET TRANSACTION STATUS SUCCESS ==========")
            print(f"[PESAPAL] Status retrieved successfully")
            print(f"[PESAPAL] ===================================================\n")
            return result, None
            
        except ValueError as e:
            print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
            print(f"[PESAPAL] ERROR: Invalid JSON response - {str(e)}")
            print(f"[PESAPAL] ===================================================\n")
            return None, f"Invalid JSON response: {str(e)}"
        except Exception as e:
            print(f"[PESAPAL] ========== GET TRANSACTION STATUS FAILED ==========")
            print(f"[PESAPAL] ERROR: Unexpected error - {str(e)}")
            print(f"[PESAPAL] ===================================================\n")
            return None, f"Unexpected error: {str(e)}"
    
    def register_ipn_url(self, ipn_url: str, ipn_notification_type: str = 'GET') -> Tuple[Optional[str], Optional[str]]:
        """
        Register IPN URL with Pesapal and get notification_id (ipn_id).
        This must be done before submitting orders if notification_id is not configured.
        
        Args:
            ipn_url: The IPN URL to register (must be publicly accessible)
            ipn_notification_type: HTTP method for IPN ('GET' or 'POST')
        
        Returns:
            Tuple of (notification_id, error_message)
        """
        print(f"\n[PESAPAL] ========== REGISTER IPN URL START ==========")
        print(f"[PESAPAL] IPN URL: {ipn_url}")
        print(f"[PESAPAL] Notification Type: {ipn_notification_type}")
        
        token = self.get_access_token()
        if not token:
            print(f"[PESAPAL] ========== REGISTER IPN URL FAILED ==========")
            print(f"[PESAPAL] ERROR: Failed to obtain access token")
            print(f"[PESAPAL] ============================================\n")
            return None, "Failed to obtain access token"
        
        endpoint = '/api/URLSetup/RegisterIPN'
        data = {
            "url": ipn_url,
            "ipn_notification_type": ipn_notification_type
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        
        print(f"[PESAPAL] Registering IPN URL with Pesapal...")
        response, error = self._make_request_with_failover('POST', endpoint, data, headers)
        
        if error:
            print(f"[PESAPAL] ========== REGISTER IPN URL FAILED ==========")
            print(f"[PESAPAL] ERROR: {error}")
            print(f"[PESAPAL] ============================================\n")
            return None, error
        
        if not response:
            print(f"[PESAPAL] ========== REGISTER IPN URL FAILED ==========")
            print(f"[PESAPAL] ERROR: No response from Pesapal API")
            print(f"[PESAPAL] ============================================\n")
            return None, "No response from Pesapal API"
        
        try:
            result = response.json()
            print(f"[PESAPAL] Response received: {json.dumps(result, indent=2)}")
            
            ipn_id = result.get('ipn_id')
            if not ipn_id:
                print(f"[PESAPAL] ========== REGISTER IPN URL FAILED ==========")
                print(f"[PESAPAL] ERROR: No ipn_id in response")
                print(f"[PESAPAL] Response: {json.dumps(result, indent=2)}")
                print(f"[PESAPAL] ============================================\n")
                return None, "No ipn_id in Pesapal API response"
            
            print(f"[PESAPAL] ========== REGISTER IPN URL SUCCESS ==========")
            print(f"[PESAPAL] IPN ID (notification_id): {ipn_id}")
            print(f"[PESAPAL] ==============================================\n")
            return ipn_id, None
            
        except ValueError as e:
            print(f"[PESAPAL] ========== REGISTER IPN URL FAILED ==========")
            print(f"[PESAPAL] ERROR: Invalid JSON response - {str(e)}")
            print(f"[PESAPAL] ============================================\n")
            return None, f"Invalid JSON response: {str(e)}"
        except Exception as e:
            print(f"[PESAPAL] ========== REGISTER IPN URL FAILED ==========")
            print(f"[PESAPAL] ERROR: Unexpected error - {str(e)}")
            print(f"[PESAPAL] ============================================\n")
            return None, f"Unexpected error: {str(e)}"






