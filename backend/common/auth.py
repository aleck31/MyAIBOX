"""
Amazon Cognito authentication provider
"""
import boto3
import time
from botocore.exceptions import ClientError
from typing import Dict, Optional
from core.config import env_config
from common.logger import logger


class CognitoAuth:
    """Amazon Cognito authentication provider"""
    
    def __init__(self):
        """Initialize Cognito client with configuration"""
        # Validate configuration
        self._validate_config()

        self.client = boto3.client('cognito-idp', region_name=env_config.aws_region)
        self.user_pool_id = env_config.cognito_config['user_pool_id']
        self.client_id = env_config.cognito_config['client_id']

        # cache for tokens and user info
        self.refresh_tokens = {}  # {username: refresh_token}
        self.access_tokens = {}   # {username: {access_token, expiry_time}}
        self.user_info = {}       # {username: {user_attributes}}
        
        # Token validity period in seconds (default: 55 minutes to be safe with 1h tokens)
        self.token_validity_period = 55 * 60
        
        logger.info(f"CognitoAuth initialized with user pool: {self.user_pool_id}")
        
    def _validate_config(self) -> None:
        """Validate authentication configuration"""
        if not env_config.cognito_config['user_pool_id']:
            error_msg = "Missing required configuration: USER_POOL_ID"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        if not env_config.cognito_config['client_id']:
            error_msg = "Missing required configuration: CLIENT_ID"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.info("Authentication configuration validated successfully")

    def authenticate(self, username: str, password: str) -> Dict:
        """
        Authenticate a user using Amazon Cognito.

        `username` is the user-entered login (Cognito username or alias such as
        email). Internally we key everything off the Cognito `sub` so downstream
        code matches the SSO path.

        Returns:
            dict: {success, tokens, sub, error}
        """
        try:
            # Initial authentication with password
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )

            # Store tokens and user info
            if 'AuthenticationResult' in response:
                access_token = response['AuthenticationResult']['AccessToken']
                user_info = self.client.get_user(AccessToken=access_token)
                attrs = {a['Name']: a['Value'] for a in user_info['UserAttributes']}
                sub = attrs.get('sub')
                if not sub:
                    raise ValueError("Cognito user has no sub attribute")

                self.refresh_tokens[sub] = response['AuthenticationResult'].get('RefreshToken')
                self.access_tokens[sub] = {
                    'access_token': access_token,
                    'expiry_time': time.time() + self.token_validity_period
                }
                self.user_info[sub] = {
                    'username': user_info['Username'],
                    'attributes': attrs,
                }

                logger.info(f"User [{username}] (sub={sub}) authenticated successfully")
                return {
                    'success': True,
                    'tokens': response['AuthenticationResult'],
                    'sub': sub,
                    'error': None,
                }
            else:
                logger.warning(f"User [{username}] authentication failed: No AuthenticationResult")
                return {'success': False, 'tokens': None, 'sub': None, 'error': 'Authentication failed'}

        except self.client.exceptions.NotAuthorizedException:
            logger.warning(f"Invalid credentials for user [{username}]")
            return {'success': False, 'tokens': None, 'sub': None, 'error': 'Invalid username or password'}

        except self.client.exceptions.UserNotFoundException:
            logger.warning(f"User [{username}] not found")
            return {'success': False, 'tokens': None, 'sub': None, 'error': 'User not found'}

        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"Authentication error for user [{username}]: {error_code} - {error_message}")
            return {'success': False, 'tokens': None, 'sub': None, 'error': error_message}

    def verify_token(self, token: str) -> Optional[str]:
        """
        Verify an access token with Cognito and refresh if expired.

        Returns the valid token (original or refreshed) on success, None otherwise.
        Caches are keyed by Cognito `sub`.
        """
        sub = None
        for s, token_data in self.access_tokens.items():
            if token_data['access_token'] == token:
                sub = s
                break

        if sub:
            current_time = time.time()
            token_expiry = self.access_tokens[sub]['expiry_time']

            if current_time < token_expiry - 300:  # 5 minutes buffer
                return token

            if sub in self.refresh_tokens:
                try:
                    if auth_result := self.refresh_access_token(sub):
                        return auth_result['AccessToken']
                except Exception as e:
                    logger.error(f"Token refresh failed for sub [{sub}]: {str(e)}")
                    self._remove_token(token)
                    return None

            try:
                self.client.get_user(AccessToken=token)
                self.access_tokens[sub]['expiry_time'] = time.time() + self.token_validity_period
                return token
            except self.client.exceptions.NotAuthorizedException:
                self._remove_token(token)
                return None
            except Exception as e:
                logger.error(f"Token verification failed: {str(e)}")
                return None

        # Verify with Cognito when no cached entry
        try:
            response = self.client.get_user(AccessToken=token)
            attrs = {a['Name']: a['Value'] for a in response['UserAttributes']}
            sub = attrs.get('sub')
            if not sub:
                logger.error("Cognito get_user returned no sub attribute")
                return None

            self.access_tokens[sub] = {
                'access_token': token,
                'expiry_time': time.time() + self.token_validity_period
            }
            self.user_info[sub] = {
                'username': response['Username'],
                'attributes': attrs,
            }
            return token

        except Exception as e:
            logger.error(f"Token verification failed: {str(e)}")
            return None

    def refresh_access_token(self, sub: str) -> Optional[Dict]:
        """Refresh access token using stored refresh token keyed by `sub`."""
        refresh_token = self.refresh_tokens.get(sub)
        if not refresh_token:
            return None

        try:
            response = self.client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow='REFRESH_TOKEN_AUTH',
                AuthParameters={'REFRESH_TOKEN': refresh_token}
            )

            if 'AuthenticationResult' in response:
                self.access_tokens[sub] = {
                    'access_token': response['AuthenticationResult']['AccessToken'],
                    'expiry_time': time.time() + self.token_validity_period
                }
                logger.info(f"Successfully refreshed token for sub [{sub}]")
                return response['AuthenticationResult']
            logger.warning(f"Token refresh failed for sub [{sub}]: No AuthenticationResult")
            return None

        except Exception as e:
            logger.error(f"Token refresh failed for sub [{sub}]: {str(e)}")
            return None

    def _remove_token(self, token: str) -> None:
        """Remove token and associated data from storage"""
        for sub, token_data in self.access_tokens.items():
            if token_data['access_token'] == token:
                if sub in self.refresh_tokens:
                    if self.refresh_access_token(sub):
                        return
                del self.access_tokens[sub]
                self.refresh_tokens.pop(sub, None)
                self.user_info.pop(sub, None)
                break

    def get_token_for_user(self, sub: str) -> str:
        """Get stored access token by `sub`."""
        token_data = self.access_tokens.get(sub)
        return token_data['access_token'] if token_data else ''

    def logout(self, token: str) -> bool:
        """
        Logout a user by invalidating their access token

        Args:
            token: The access token to invalidate

        Returns:
            bool: True if logout successful, False otherwise
        """
        try:
            # Get user info before invalidating token
            self.client.global_sign_out(
                AccessToken=token
            )
            
            # Clean up stored data
            self._remove_token(token)
            logger.info("User logged out successfully")
            return True
            
        except Exception as e:
            logger.error(f"Logout failed: {str(e)}")
            return False

# Create a singleton instance
cognito_auth = CognitoAuth()
