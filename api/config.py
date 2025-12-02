"""
API Configuration Module
Manages environment variables and API endpoints
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


class APIConfig:
    """Configuration class for API endpoints and settings"""

    # Base URLs for different environments
    API_TEST_URL = os.getenv('API_TEST_URL', 'https://test.mlm.rapsodo.com')
    API_STAGING_URL = os.getenv('API_STAGING_URL', '')
    API_PROD_URL = os.getenv('API_PROD_URL', 'https://mlm.rapsodo.com')

    # Default environment (test, staging, prod)
    DEFAULT_ENV = os.getenv('TEST_ENV', 'test')

    # Request timeout settings (in seconds)
    DEFAULT_TIMEOUT = int(os.getenv('API_TIMEOUT', '30'))
    
    # Retry settings
    MAX_RETRIES = int(os.getenv('API_MAX_RETRIES', '3'))
    RETRY_BACKOFF_FACTOR = float(os.getenv('API_RETRY_BACKOFF', '0.5'))

    @classmethod
    def get_base_url(cls, env=None):
        """
        Get the base URL for the specified environment
        
        Args:
            env: Environment name (test, staging, prod). If None, uses DEFAULT_ENV
            
        Returns:
            str: Base URL for the environment
        """
        env = env or cls.DEFAULT_ENV
        env = env.lower()
        
        url_map = {
            'test': cls.API_TEST_URL,
            'staging': cls.API_STAGING_URL,
            'prod': cls.API_PROD_URL
        }
        
        return url_map.get(env, cls.API_TEST_URL)

    @classmethod
    def get_full_url(cls, endpoint, env=None):
        """
        Get the full URL for an endpoint
        
        Args:
            endpoint: API endpoint path (e.g., '/auth/register')
            env: Environment name (optional)
            
        Returns:
            str: Full URL
        """
        base_url = cls.get_base_url(env)
        # Ensure endpoint starts with /
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        return f"{base_url}{endpoint}"

