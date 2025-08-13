"""
Centralized AWS configuration and client creation
"""
import os
import ast
import boto3
from typing import Optional, Dict, Any
from botocore.config import Config
from core.config import env_config
from core.logger import logger

# Global session cache - dictionary to store sessions by region and role
_AWS_SESSION = {}

def get_aws_session(region_name: Optional[str] = None) -> boto3.Session:
    """Get configured AWS session with optional role assumption

    Parameters
    ----------
    region_name :
        AWS Region name. If not specified, uses the default region_name from env_config
    """
    global _AWS_SESSION

    # Use provided region_name or default from config
    region_name = region_name or env_config.aws_region

    # Create a cache key based on region and role ARN
    cache_key = f"{region_name}"
    
    # Return cached session if it exists
    if cache_key in _AWS_SESSION:
        return _AWS_SESSION[cache_key]

    # Initialize session kwargs
    session_kwargs: Dict[str, Any] = {"region_name": region_name}
    
    # Add profile if specified in environment
    if profile_name := os.environ.get("AWS_PROFILE"):
        logger.info(f"Using AWS profile: {profile_name}")
        session_kwargs["profile_name"] = profile_name

    try:
        # Create new session since none exists in cache
        session = boto3.Session(**session_kwargs)
        
        # Cache the session
        _AWS_SESSION[cache_key] = session
        
        return session
        
    except Exception as e:
        logger.error(f"Failed to create AWS session: {str(e)}")
        raise

def get_aws_client(service_name: str, region_name: Optional[str] = None):
    """Get configured AWS client for a specific service

    Parameters
    ----------
    service_name :
        Name of the AWS service (e.g., 's3', 'dynamodb', etc.)
    region_name :
        Optional region_name override. If not specified, uses the default region
    """
    try:
        session = get_aws_session(region_name=region_name)
        # Configure retry settings
        config = Config(
            region_name=region_name or env_config.aws_region,
            retries={
                "max_attempts": 10,
                "mode": "standard",
            },
        )
        return session.client(service_name=service_name, config=config)

    except Exception as e:
        logger.error(f"Error creating AWS client for {service_name}: {e}")
        raise

def get_aws_resource(service_name: str, region_name: Optional[str] = None):
    """Get configured AWS resource for a specific service

    Parameters
    ----------
    service_name :
        Name of the AWS service (e.g., 's3', 'dynamodb', etc.)
    region_name :
        Optional region_name override. If not specified, uses the default region
    """
    try:
        session = get_aws_session(region_name=region_name)
        return session.resource(service_name=service_name)
    except Exception as e:
        logger.error(f"Error creating AWS resource for {service_name}: {e}")
        raise


def get_secret(secret_name):
    '''Get user dict from Secrets Manager'''
    try:
        # Get Secrets Manager client using centralized AWS configuration
        client = get_aws_client('secretsmanager')
        
        response = client.get_secret_value(
            SecretId=secret_name
        )
        
        # Decrypts secret using the associated KMS key.
        secret = ast.literal_eval(response['SecretString'])
        return secret
        
    except Exception as ex:
        logger.error(f"Error getting secret {secret_name}: {str(ex)}")
        raise

def translate_text(text, target_lang_code):
    '''
    Translates input text to the target language. Supported languages: 
    https://docs.aws.amazon.com/translate/latest/dg/what-is-languages.html
    '''
    client = get_aws_client(
        service_name='translate'
    )

    # Initialize variables with default values
    translated_text = None
    source_lang_code = None

    try:
        # Call TranslateText API
        response = client.translate_text(
            Text=text,
            SourceLanguageCode='auto',
            TargetLanguageCode=target_lang_code)

        # Get translated text and detected source language code
        translated_text = response['TranslatedText']
        source_lang_code = response['SourceLanguageCode']

    except Exception as ex:
        # Log error and set result & source_lang_code to None if fails
        logger.error(ex)

    return {
        'translated_text': translated_text,
        'source_lang_code': source_lang_code
    }
