"""
Base API Client
Provides common HTTP methods and error handling for all API clients
"""

import requests
from typing import Optional, Dict, Any
from base.logger import Logger
from api.config import APIConfig


class APIResponse:
    """Wrapper class for API responses"""
    
    def __init__(self, response: requests.Response):
        self.response = response
        self.status_code = response.status_code
        self.headers = response.headers
        
        # Try to parse JSON response
        try:
            self.json_data = response.json()
            self.success = self.json_data.get('success', False)
            self.message = self.json_data.get('message', '')
            self.data = self.json_data.get('data', {})
            self.error_code = self.json_data.get('errorCode', None)
        except ValueError:
            self.json_data = {}
            self.success = False
            self.message = 'Failed to parse JSON response'
            self.data = {}
            self.error_code = None
        
        self.text = response.text
    
    def is_success(self) -> bool:
        """Check if the API call was successful"""
        return self.status_code == 200 and self.success
    
    def __repr__(self):
        return f"APIResponse(status={self.status_code}, success={self.success})"


class BaseAPIClient:
    """
    Base API client with common HTTP methods
    All specific API clients should inherit from this class
    """
    
    def __init__(self, env: Optional[str] = None):
        """
        Initialize the API client
        
        Args:
            env: Environment to use (test, staging, prod). Defaults to TEST_ENV from config
        """
        self.env = env or APIConfig.DEFAULT_ENV
        self.base_url = APIConfig.get_base_url(self.env)
        self.timeout = APIConfig.DEFAULT_TIMEOUT
        self.session = requests.Session()
        self.logger = Logger()
        
        # Default headers
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint"""
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        return f"{self.base_url}{endpoint}"
    
    def _log_request(self, method: str, url: str, **kwargs):
        """Log API request details"""
        self.logger.info(f"API Request: {method} {url}")
        if 'json' in kwargs:
            self.logger.debug(f"Request Body: {kwargs['json']}")
    
    def _log_response(self, response: APIResponse):
        """Log API response details"""
        self.logger.info(f"API Response: {response.status_code} - Success: {response.success}")
        # Log response body for debugging
        if response.json_data:
            self.logger.debug(f"Response Body: {response.json_data}")
        
        if not response.is_success():
            self.logger.error(f"Error: {response.message} (Code: {response.error_code})")
    
    def set_auth_token(self, token: str):
        """
        Set authorization token for all subsequent requests
        
        Args:
            token: JWT token (with or without 'JWT ' prefix)
        """
        # Ensure token has 'JWT ' prefix
        if not token.startswith('JWT '):
            token = f'JWT {token}'
        self.session.headers.update({'Authorization': token})
        self._stored_token = token  # Store the token for retrieval
        self.logger.info("Authorization token set")
    
    def get_auth_token(self) -> str:
        """
        Get the stored authorization token
        
        Returns:
            str: The stored JWT token (with 'JWT ' prefix)
        
        Raises:
            ValueError: If no token has been set
        """
        if not hasattr(self, '_stored_token'):
            raise ValueError("No auth token available. Please login first.")
        return self._stored_token
    
    def clear_auth_token(self):
        """Remove authorization token"""
        if 'Authorization' in self.session.headers:
            del self.session.headers['Authorization']
        self.logger.info("Authorization token cleared")
    
    def set_user_data(self, user_data: Dict[str, Any]):
        """
        Store user data from login response
        
        Args:
            user_data: User data dictionary from login response
        """
        self._stored_user_data = user_data
        self.logger.info("User data stored")
    
    def get_user_data(self) -> Dict[str, Any]:
        """
        Get the stored user data
        
        Returns:
            Dict[str, Any]: The stored user data from login
        
        Raises:
            ValueError: If no user data has been stored
        """
        if not hasattr(self, '_stored_user_data'):
            raise ValueError("No user data available. Please login first.")
        return self._stored_user_data
    
    def set_header(self, key: str, value: str):
        """
        Set a custom header
        
        Args:
            key: Header name
            value: Header value
        """
        self.session.headers.update({key: value})
    
    def get(self, endpoint: str, params: Optional[Dict] = None, **kwargs) -> APIResponse:
        """
        Send GET request
        
        Args:
            endpoint: API endpoint
            params: Query parameters
            **kwargs: Additional arguments for requests.get()
            
        Returns:
            APIResponse object
        """
        url = self._build_url(endpoint)
        self._log_request('GET', url, params=params)
        
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout,
                **kwargs
            )
            api_response = APIResponse(response)
            self._log_response(api_response)
            return api_response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"GET request failed: {str(e)}")
            raise
    
    def post(self, endpoint: str, json_data: Optional[Dict] = None, **kwargs) -> APIResponse:
        """
        Send POST request
        
        Args:
            endpoint: API endpoint
            json_data: JSON request body
            **kwargs: Additional arguments for requests.post()
            
        Returns:
            APIResponse object
        """
        url = self._build_url(endpoint)
        self._log_request('POST', url, json=json_data)
        
        try:
            response = self.session.post(
                url,
                json=json_data,
                timeout=self.timeout,
                **kwargs
            )
            api_response = APIResponse(response)
            self._log_response(api_response)
            return api_response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"POST request failed: {str(e)}")
            raise
    
    def put(self, endpoint: str, json_data: Optional[Dict] = None, **kwargs) -> APIResponse:
        """
        Send PUT request
        
        Args:
            endpoint: API endpoint
            json_data: JSON request body
            **kwargs: Additional arguments for requests.put()
            
        Returns:
            APIResponse object
        """
        url = self._build_url(endpoint)
        self._log_request('PUT', url, json=json_data)
        
        try:
            response = self.session.put(
                url,
                json=json_data,
                timeout=self.timeout,
                **kwargs
            )
            api_response = APIResponse(response)
            self._log_response(api_response)
            return api_response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"PUT request failed: {str(e)}")
            raise
    
    def delete(self, endpoint: str, **kwargs) -> APIResponse:
        """
        Send DELETE request
        
        Args:
            endpoint: API endpoint
            **kwargs: Additional arguments for requests.delete()
            
        Returns:
            APIResponse object
        """
        url = self._build_url(endpoint)
        self._log_request('DELETE', url)
        
        try:
            response = self.session.delete(
                url,
                timeout=self.timeout,
                **kwargs
            )
            api_response = APIResponse(response)
            self._log_response(api_response)
            return api_response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"DELETE request failed: {str(e)}")
            raise
    
    def patch(self, endpoint: str, json_data: Optional[Dict] = None, **kwargs) -> APIResponse:
        """
        Send PATCH request
        
        Args:
            endpoint: API endpoint
            json_data: JSON request body
            **kwargs: Additional arguments for requests.patch()
            
        Returns:
            APIResponse object
        """
        url = self._build_url(endpoint)
        self._log_request('PATCH', url, json=json_data)
        
        try:
            response = self.session.patch(
                url,
                json=json_data,
                timeout=self.timeout,
                **kwargs
            )
            api_response = APIResponse(response)
            self._log_response(api_response)
            return api_response
        except requests.exceptions.RequestException as e:
            self.logger.error(f"PATCH request failed: {str(e)}")
            raise

