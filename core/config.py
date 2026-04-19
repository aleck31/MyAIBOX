"""
Configuration management using python-dotenv for environment variables
"""
import os
from typing import Any, Dict, Union, List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Debug: Print loaded environment variables
print(f"Loaded SERVER_HOST: {os.getenv('SERVER_HOST')}")


class ENVConfig:
    """Environment-specific configuration for deployment settings"""
    
    @property
    def aws_region(self) -> str:
        """Get default AWS region"""
        return os.getenv('AWS_REGION', 'ap-southeast-1')

    @property
    def cognito_config(self) -> dict:
        """Get Cognito configuration"""
        return {
            'user_pool_id': os.getenv('USER_POOL_ID'),
            'client_id': os.getenv('CLIENT_ID')
        }

    @property
    def database_config(self) -> dict:
        """Get database configuration"""
        return {
            'setting_table': os.getenv('SETTING_TABLE', 'aibox_setting'),
            'session_table': os.getenv('SESSION_TABLE', 'aibox_session'),
            'retention_days': int(os.getenv('RETENTION_DAYS', '30')) # 用于计算dynamodb ttl
        }

    @property
    def bedrock_config(self) -> Dict[str, str]:
        """Get AWS Bedrock configuration"""
        return {
            'region_name': os.getenv('BEDROCK_REGION', 'us-west-2'),  # Changed from region_id to aws_region
            'assume_role': os.getenv('BEDROCK_ASSUME_ROLE', '')
        }

    @property
    def sandbox_config(self) -> Dict[str, Union[str, int, List[str]]]:
        """Get EC2 Sandbox Env configuration"""
        # Get allowed runtimes as a list from space-separated string
        allowed_runtimes_str = os.getenv('ALLOWED_RUNTIMES', 'python3 python node bash sh')
        allowed_runtimes = allowed_runtimes_str.split() if allowed_runtimes_str else []
        return {
            'instance_id': os.getenv('INSTANCE_ID', ''),
            'region': os.getenv('REGION', 'ap-northeast-1'),
            'aws_profile': os.getenv('AWS_PROFILE', 'lab'),
            'base_sandbox_dir': os.getenv('BASE_SANDBOX_DIR', '/opt/sandbox'),
            'max_execution_time': int(os.getenv('MAX_EXECUTION_TIME', '900')),
            'max_memory_mb': int(os.getenv('MAX_MEMORY_MB', '1024')),
            'cleanup_after_hours': int(os.getenv('CLEANUP_AFTER_HOURS', '48')),
            'allowed_runtimes': allowed_runtimes
        }

    @property
    def gemini_config(self) -> Dict[str, str]:
        """Get Gemini API configuration"""
        return {
            # Default secret ID for AgentCore deployment
            'secret_id': os.getenv('GEMINI_SECRET_ID', 'dev_gemini_api')
        }

    @property
    def openai_config(self) -> Dict[str, str]:
        """Get OpenAI API configuration"""
        return {
            # Default secret ID for AgentCore deployment
            'secret_id': os.getenv('OPENAI_SECRET_ID', 'dev_openai_api'),
        }

    @property
    def sso_config(self) -> Dict[str, Any]:
        """Get SSO configuration.

        When enabled, the app reads the SSO session cookie and validates it
        against `<SSO_AUTH_ORIGIN>/introspect`. When disabled, the app keeps
        using Cognito USER_PASSWORD_AUTH via common/auth.py.
        """
        enabled = os.getenv('SSO_ENABLED', 'false').lower() == 'true'
        auth_origin = os.getenv('SSO_AUTH_ORIGIN', '').rstrip('/')
        cookie_name = os.getenv('SSO_COOKIE_NAME', '')
        if enabled and (not auth_origin or not cookie_name):
            raise RuntimeError(
                "SSO_ENABLED=true requires SSO_AUTH_ORIGIN and SSO_COOKIE_NAME to be set"
            )
        return {
            'enabled': enabled,
            'auth_origin': auth_origin,
            'cookie_name': cookie_name,
            'cache_ttl': int(os.getenv('SSO_CACHE_TTL', '30')),
            'stale_grace_ttl': int(os.getenv('SSO_STALE_GRACE_TTL', '60')),
            'request_timeout': float(os.getenv('SSO_REQUEST_TIMEOUT', '5')),
        }

    @property
    def agentcore_config(self) -> Dict[str, Any]:
        """Get AgentCore Runtime configuration"""
        return {
            'enabled': os.getenv('USE_AGENTCORE', 'false').lower() == 'true',
            'runtime_arn': os.getenv('AGENTCORE_RUNTIME_ARN', ''),
            'region': os.getenv('AGENTCORE_REGION', os.getenv('AWS_REGION', 'ap-southeast-1')),
            'endpoint_name': os.getenv('AGENTCORE_ENDPOINT_NAME', 'DEFAULT'),
        }


class AppConfig:
    """Application-level configuration settings"""

    @property
    def server_config(self) -> Dict[str, Any]:
        """Get server configuration"""
        return {
            'host': os.getenv('SERVER_HOST', 'localhost'),
            'port': int(os.getenv('SERVER_PORT', '8080')),
            'debug': os.getenv('DEBUG', 'False').lower() == 'true',
            'log_level': 'debug' if os.getenv('DEBUG') else 'info'
        }

    @property
    def cors_config(self) -> Dict[str, Any]:
        """Get CORS configuration"""
        origins = [o.strip() for o in os.getenv('CORS_ORIGINS', '*').split(',') if o.strip()]
        # Browsers reject `Access-Control-Allow-Origin: *` together with credentials,
        # and SessionMiddleware always sends a cookie. Force an explicit origin list.
        if '*' in origins:
            raise RuntimeError(
                "CORS_ORIGINS='*' is not allowed with credentialed requests. "
                "Set CORS_ORIGINS to an explicit comma-separated list of origins."
            )
        return {
            'allow_origins': origins,
            'allow_methods': os.getenv('CORS_METHODS', 'GET,POST,PUT,DELETE,OPTIONS').split(','),
            'allow_headers': os.getenv('CORS_HEADERS', '*').split(',')
        }

    @property
    def security_config(self) -> Dict[str, Any]:
        """Get security configuration"""
        secret_key = os.getenv('SECRET_KEY')
        # Session cookies are signed with this key; a known/default value lets anyone forge sessions.
        _known_defaults = {
            'default-secret-key',
            'replace-me-with-a-random-48-byte-token',
            'aibox-production-secret-key-2024',
            'aibox-production-secret-key-2025',
        }
        if not secret_key or secret_key in _known_defaults:
            raise RuntimeError(
                "SECRET_KEY is unset or uses a known default. "
                "Generate a strong value, e.g. `python -c 'import secrets; print(secrets.token_urlsafe(48))'`."
            )
        return {
            'secret_key': secret_key,
            'token_expiration': int(os.getenv('TOKEN_EXPIRATION', '7200')),
            'ssl_enabled': os.getenv('SSL_ENABLED', 'False').lower() == 'true'
        }


# Create singleton instances
env_config = ENVConfig()
app_config = AppConfig()
