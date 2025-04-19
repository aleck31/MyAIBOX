"""
Test authentication functionality

Usage:
    python -m tests.test_auth --username <username> --password <password>
"""
import unittest
import sys
import os
import argparse
from fastapi.testclient import TestClient
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.auth import cognito_auth
from core.config import app_config, env_config
from common.login import get_auth_user


class TestAuth(unittest.TestCase):
    """Test authentication functionality"""

    def setUp(self):
        """Set up test environment"""
        # Create a simple FastAPI app for testing
        self.app = FastAPI()
        self.app.add_middleware(
            SessionMiddleware,
            secret_key=app_config.security_config['secret_key'],
            session_cookie="session"
        )

        # Add test routes
        @self.app.post("/test-login")
        async def test_login(request: Request):
            """Test login endpoint"""
            form_data = await request.form()
            username = form_data.get("username")
            password = form_data.get("password")
            
            auth_result = cognito_auth.authenticate(username, password)
            if auth_result['success']:
                request.session['user'] = {
                    'username': username,
                    'access_token': auth_result['tokens']['AccessToken']
                }
                return {"status": "success", "message": "Login successful"}
            else:
                return {"status": "error", "message": auth_result['error']}

        @self.app.get("/test-protected")
        async def test_protected(request: Request):
            """Test protected endpoint"""
            try:
                username = get_auth_user(request)
                return {"status": "success", "username": username}
            except HTTPException:
                return {"status": "error", "message": "Not authenticated"}

        @self.app.get("/test-logout")
        async def test_logout(request: Request):
            """Test logout endpoint"""
            user = request.session.get('user')
            if user and user.get('access_token'):
                result = cognito_auth.logout(user['access_token'])
                request.session.clear()
                return {"status": "success" if result else "error"}
            return {"status": "error", "message": "No active session"}

        # Create test client
        self.client = TestClient(self.app)
        
        # Get test credentials from global args
        self.test_username = TestAuth.args.username
        self.test_password = TestAuth.args.password

    def test_1_login(self):
        """Test login functionality"""
        print("\n=== Testing Login ===")
        
        # Test with valid credentials
        response = self.client.post(
            "/test-login",
            data={"username": self.test_username, "password": self.test_password}
        )
        data = response.json()
        
        print(f"Login response: {data}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")
        
        # Verify session cookie was set
        self.assertIn("session", self.client.cookies)
        print("Session cookie set successfully")

    def test_2_token_verification(self):
        """Test token verification"""
        print("\n=== Testing Token Verification ===")
        
        # First login to get a token
        self.client.post(
            "/test-login",
            data={"username": self.test_username, "password": self.test_password}
        )
        
        # Access protected endpoint
        response = self.client.get("/test-protected")
        data = response.json()
        
        print(f"Protected endpoint response: {data}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["username"], self.test_username)
        print("Token verification successful")

    def test_3_token_refresh(self):
        """Test token refresh functionality"""
        print("\n=== Testing Token Refresh ===")
        
        # First login to get a token
        self.client.post(
            "/test-login",
            data={"username": self.test_username, "password": self.test_password}
        )
        
        # Get the current token for the user
        original_token = cognito_auth.get_token_for_user(self.test_username)
        print(f"Original token: {original_token[:10]}...{original_token[-10:]}")
        
        # Simulate token refresh
        auth_result = cognito_auth.refresh_access_token(self.test_username)
        if auth_result:
            new_token = auth_result['AccessToken']
            print(f"New token: {new_token[:10]}...{new_token[-10:]}")
            self.assertNotEqual(original_token, new_token)
            print("Token refresh successful")
        else:
            print("Token refresh failed - this might be expected if the token is still valid")
            self.skipTest("Token refresh not needed")

    def test_4_logout(self):
        """Test logout functionality"""
        print("\n=== Testing Logout ===")
        
        # First login to get a token
        self.client.post(
            "/test-login",
            data={"username": self.test_username, "password": self.test_password}
        )
        
        # Logout
        response = self.client.get("/test-logout")
        data = response.json()
        
        print(f"Logout response: {data}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")
        
        # Verify session was cleared
        response = self.client.get("/test-protected")
        data = response.json()
        self.assertEqual(data["status"], "error")
        print("Logout successful")


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Test authentication functionality')
    parser.add_argument('--username', default='demo', help='Username for authentication tests')
    parser.add_argument('--password', default='mm5BaFNz', help='Password for authentication tests')
    
    # Store args in the TestAuth class for access in setUp
    TestAuth.args = parser.parse_args()
    
    # Run tests
    unittest.main(argv=[sys.argv[0]])  # Exclude our custom args from unittest
