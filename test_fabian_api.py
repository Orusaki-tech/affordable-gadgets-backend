#!/usr/bin/env python3
"""
Test Fabian's login via API calls.
Usage: python3 test_fabian_api.py [API_BASE_URL]
Example: python3 test_fabian_api.py http://localhost:8000
         python3 test_fabian_api.py https://your-api.railway.app
"""
import sys
import requests
import json

def test_login(api_base_url, email, password):
    """Test login API endpoint."""
    url = f"{api_base_url}/api/auth/token/login/"
    
    print("="*70)
    print("TESTING FABIAN'S LOGIN VIA API")
    print("="*70)
    print(f"API Base URL: {api_base_url}")
    print(f"Email: {email}")
    print(f"\nTesting login endpoint: {url}")
    print()
    
    try:
        response = requests.post(
            url,
            data={
                'username': email,
                'password': password
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            timeout=10
        )
        
        print(f"HTTP Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()
        
        try:
            response_data = response.json()
            print("Response Body:")
            print(json.dumps(response_data, indent=2))
        except:
            print("Response Body (text):")
            print(response.text)
        
        print()
        
        if response.status_code == 200:
            token = response_data.get('token')
            if token:
                print("✅ LOGIN SUCCESS!")
                print(f"Token received: {token[:20]}...")
                print()
                
                # Test admin profile endpoint
                return test_admin_profile(api_base_url, token)
            else:
                print("⚠️  Login returned 200 but no token in response")
                return False
        else:
            print("❌ LOGIN FAILED")
            print()
            print("Possible reasons:")
            print("  - Invalid credentials")
            print("  - User does not have is_staff=True")
            print("  - User account is inactive")
            print("  - Server error")
            
            # Try to get more details from error response
            if response.status_code == 400:
                try:
                    error_data = response.json()
                    if 'non_field_errors' in error_data:
                        print(f"\nError details: {error_data['non_field_errors']}")
                except:
                    pass
            
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Could not connect to server")
        print(f"   Make sure the server is running at {api_base_url}")
        return False
    except requests.exceptions.Timeout:
        print("❌ ERROR: Request timed out")
        return False
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_admin_profile(api_base_url, token):
    """Test admin profile retrieval."""
    url = f"{api_base_url}/api/inventory/profiles/admin/"
    
    print("="*70)
    print("TESTING ADMIN PROFILE RETRIEVAL")
    print("="*70)
    print(f"Testing endpoint: {url}")
    print()
    
    try:
        response = requests.get(
            url,
            headers={
                'Authorization': f'Token {token}',
                'Content-Type': 'application/json'
            },
            timeout=10
        )
        
        print(f"HTTP Status Code: {response.status_code}")
        print()
        
        try:
            response_data = response.json()
            print("Response Body:")
            print(json.dumps(response_data, indent=2))
        except:
            print("Response Body (text):")
            print(response.text)
        
        print()
        
        if response.status_code == 200:
            print("✅ ADMIN PROFILE RETRIEVAL SUCCESS!")
            print("✅ Full login flow works correctly!")
            return True
        else:
            print("⚠️  Login succeeded but admin profile retrieval failed")
            print("   This might indicate a permission issue")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    api_base_url = sys.argv[1] if len(sys.argv) > 1 else 'http://localhost:8000'
    email = "fabian@shwariphones.com"
    password = "00000000"
    
    success = test_login(api_base_url, email, password)
    sys.exit(0 if success else 1)
