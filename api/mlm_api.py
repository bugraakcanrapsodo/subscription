"""
MLM API Client
Handles all MLM backend operations including authentication, subscriptions, devices, and licenses
"""

from typing import Optional, Dict, Any
from api.base_client import BaseAPIClient, APIResponse
from models.subscription import (
    WebPlansResponse, 
    CreateWebSubscriptionResponse, 
    GetSubscriptionsResponse,
    CancelWebSubscriptionResponse,
    ReactivateWebSubscriptionResponse,
    GetAGLicenseResponse
)


class MlmAPI(BaseAPIClient):
    """
    MLM API client for all backend operations:
    - User authentication (register, login)
    - Device registration
    - Subscription management (web plans, create, cancel, reactivate)
    - Awesome Golf licenses
    - User account management
    """
    
    def __init__(self, env: Optional[str] = None):
        """
        Initialize the MLM API client
        
        Args:
            env: Environment to use (test, staging, prod)
        """
        super().__init__(env)
        self.logger.info("MlmAPI client initialized")
    
    def register(
        self,
        email: str,
        first_name: str = "Test",
        last_name: str = "User",
        password: str = "Aa123456",
        password_confirmation: Optional[str] = None,
        birth_date: str = "1990-01-01",
        hand: str = "Right-Handed",
        unit: str = "imperial",
        country: int = 1,
        gender: int = 2,
        handicap_id: int = 1,
        purchased_from: Optional[Dict[str, Any]] = None,
        zip_code: str = "35580",
        lang: Optional[str] = None
    ) -> APIResponse:
        """
        Register a new user
        
        API Endpoint: POST /auth/register
        
        Args:
            email: User email address (REQUIRED)
            first_name: User's first name (default: "Test")
            last_name: User's last name (default: "User")
            password: Password (default: "Aa123456")
            password_confirmation: Password confirmation (default: matches password)
            birth_date: Birth date in format "YYYY-MM-DD" (default: "1990-01-01")
            hand: Hand preference (default: "Right-Handed")
            unit: Unit preference (default: "imperial")
            country: Country ID (default: 1)
            gender: Gender ID (default: 2)
            handicap_id: Handicap ID (default: 1)
            purchased_from: Dict with 'code' (int) and 'text' (str) keys (default: {"code": 5, "text": "Other"})
            zip_code: ZIP/postal code (default: "35580")
            lang: Language code (optional, e.g., "jp", "en")
        
        Returns:
            APIResponse: Response containing user data including:
                - id, _id
                - email, firstName, lastName
                - isVerified, registerConfirmationToken
                - country, gender, handicapId
                - and other user fields
        
        Example:
            >>> mlm = MlmAPI()
            >>> # Simple registration with just email
            >>> response = mlm.register(email="test@example.com")
            >>> 
            >>> # Custom registration
            >>> response = mlm.register(
            ...     email="test@example.com",
            ...     first_name="John",
            ...     last_name="Doe",
            ...     password="CustomPass123"
            ... )
            >>> assert response.is_success()
        """
        endpoint = "/auth/register"
        
        # Set password_confirmation to match password if not provided
        if password_confirmation is None:
            password_confirmation = password
        
        # Set default purchased_from if not provided
        if purchased_from is None:
            purchased_from = {"code": 5, "text": "Other"}
        
        # Build request body
        body = {
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "password": password,
            "passwordConfirmation": password_confirmation,
            "birthDate": birth_date,
            "hand": hand,
            "unit": unit,
            "country": country,
            "gender": gender,
            "handicapId": handicap_id,
            "purchasedFrom": purchased_from,
            "zipCode": zip_code
        }
        
        # Set language header if provided
        if lang:
            self.set_header("lang", lang)
        
        self.logger.info(f"Registering user: {email}")
        response = self.post(endpoint, json_data=body)
        
        # Clear language header after request if it was set
        if lang and 'lang' in self.session.headers:
            del self.session.headers['lang']
        
        return response
    
    def register_device(
        self,
        registered_mac: str,
        registered_serial: str = "mlm2proserial"
    ) -> APIResponse:
        """
        Register a device for the authenticated user
        
        API Endpoint: POST /user/registeredDevice
        
        Args:
            registered_mac: MAC address of the device
            registered_serial: Serial number of the device (default: "mlm2proserial")
        
        Returns:
            APIResponse: Device registration result
        
        Note: Requires authentication token to be set
        """
        endpoint = "/user/registeredDevice"
        
        body = {
            "registeredMac": registered_mac,
            "registeredSerial": registered_serial
        }
        
        self.logger.info(f"Registering device - Serial: {registered_serial}")
        response = self.post(endpoint, json_data=body)
        
        return response
    
    def login(self, email: str, password: str) -> APIResponse:
        """
        Login with email and password
        
        API Endpoint: POST /auth/login
        
        Args:
            email: User email address
            password: User password
        
        Returns:
            APIResponse: Response containing JWT token and user data
        
        Example:
            >>> mlm = MlmAPI()
            >>> response = mlm.login("test@example.com", "TestPass123")
            >>> if response.is_success():
            ...     token = response.data.get('token')
            ...     mlm.set_auth_token(token)
        """
        endpoint = "/auth/login"
        body = {
            "email": email,
            "password": password
        }
        
        self.logger.info(f"Logging in user: {email}")
        response = self.post(endpoint, json_data=body)
        
        # Automatically set auth token and user data if login successful
        if response.is_success():
            # Token is in the root of the response
            token = response.json_data.get('token')
            
            if token:
                self.set_auth_token(token)
            else:
                self.logger.warning("Login successful but no token found in response")
            
            # Store user data from response
            user_data = response.json_data.get('data')
            if user_data:
                self.set_user_data(user_data)
            else:
                self.logger.warning("Login successful but no user data found in response")
        
        return response
    
    def get_web_plans(self, country: str = "us") -> WebPlansResponse:
        """
        Get available web subscription plans for a country
        
        API Endpoint: GET /subscription/web/plans
        
        Args:
            country: Country code (default: "us")
        
        Returns:
            WebPlansResponse: Pydantic model with plans data and helper methods
        
        Note: Requires authentication token to be set
        
        Example:
            >>> mlm = MlmAPI()
            >>> mlm.login("test@example.com", "Aa123456")
            >>> plans_response = mlm.get_web_plans(country="us")
            >>> 
            >>> # Get eligible plans
            >>> eligible = plans_response.get_eligible_plans()
            >>> for plan in eligible:
            ...     print(f"{plan['name']}: {plan['code']}")
        """
        endpoint = "/subscription/web/plans"
        params = {"country": country}
        
        self.logger.info(f"Getting web plans for country: {country}")
        response = self.get(endpoint, params=params)
        
        if response.is_success():
            # Parse response into Pydantic model
            plans_data = WebPlansResponse(**response.json_data)
            return plans_data
        else:
            raise Exception(f"Failed to get web plans: {response.message}")
    
    def create_web_subscription(
        self,
        plan_code: int,
        cancel_url: str = "https://test.mlm.rapsodo.com/mlm-web",
        success_url: str = "https://test.mlm.rapsodo.com/mlm-web/profile/membership?success"
    ) -> CreateWebSubscriptionResponse:
        """
        Create a web subscription and get Stripe checkout session URL
        
        API Endpoint: POST /subscription/web/create
        
        Args:
            plan_code: Plan code (e.g., 1 for oneYearSubscription, 9 for twoYearsSubscription)
            cancel_url: URL to redirect on cancel (default: test MLM web)
            success_url: URL to redirect on success (default: test MLM profile)
        
        Returns:
            CreateWebSubscriptionResponse: Response with Stripe checkout session URL
        
        Note: Requires authentication token to be set
        
        Example:
            >>> mlm = MlmAPI()
            >>> mlm.login("test@example.com", "Aa123456")
            >>> 
            >>> # Get eligible plans first
            >>> plans = mlm.get_web_plans()
            >>> eligible = plans.get_eligible_plans()
            >>> 
            >>> # Create subscription with first eligible plan
            >>> result = mlm.create_web_subscription(plan_code=eligible[0]['code'])
            >>> checkout_url = result.session.url
            >>> print(f"Checkout URL: {checkout_url}")
        """
        endpoint = "/subscription/web/create"
        
        body = {
            "cancel_url": cancel_url,
            "success_url": success_url,
            "type": plan_code
        }
        
        self.logger.info(f"Creating web subscription with plan code: {plan_code}")
        response = self.post(endpoint, json_data=body)
        
        if response.is_success():
            # Parse response into Pydantic model
            subscription_data = CreateWebSubscriptionResponse(**response.json_data)
            return subscription_data
        else:
            raise Exception(f"Failed to create web subscription: {response.message}")
    
    def get_subscriptions(self) -> GetSubscriptionsResponse:
        """
        Get all subscriptions for the authenticated user
        
        API Endpoint: GET /subscription
        
        Returns:
            GetSubscriptionsResponse: Pydantic model containing subscription list
        
        Note: Requires authentication token to be set
        
        Example:
            >>> mlm = MlmAPI()
            >>> mlm.login("test@example.com", "Aa123456")
            >>> subscriptions = mlm.get_subscriptions()
            >>> 
            >>> if subscriptions.has_active_subscription():
            ...     latest = subscriptions.get_latest_subscription()
            ...     print(f"Latest subscription ID: {latest.id}")
            ...     print(f"Status: {latest.status}")
            ...     print(f"Expires: {latest.expireDate}")
        """
        endpoint = "/subscription"
        
        self.logger.info("Getting user subscriptions")
        response = self.get(endpoint)
        
        if response.is_success():
            # Parse response into Pydantic model
            subscriptions_data = GetSubscriptionsResponse(**response.json_data)
            self.logger.info(f"Found {len(subscriptions_data.subscriptions)} subscription(s)")
            return subscriptions_data
        else:
            raise Exception(f"Failed to get subscriptions: {response.message}")
    
    def cancel_web_subscription(self) -> CancelWebSubscriptionResponse:
        """
        Cancel the user's web subscription
        
        API Endpoint: POST /subscription/web/cancel
        
        Returns:
            CancelWebSubscriptionResponse: Pydantic model with success status
        
        Note: Requires authentication token to be set
        
        Example:
            >>> mlm = MlmAPI()
            >>> mlm.login("test@example.com", "Aa123456")
            >>> result = mlm.cancel_web_subscription()
            >>> if result.success:
            ...     print("Subscription cancelled successfully")
        """
        endpoint = "/subscription/web/cancel"
        
        self.logger.info("Cancelling web subscription")
        response = self.post(endpoint, json_data={})
        
        if response.is_success():
            # Parse response into Pydantic model
            cancel_data = CancelWebSubscriptionResponse(**response.json_data)
            self.logger.info("Web subscription cancelled successfully")
            return cancel_data
        else:
            raise Exception(f"Failed to cancel web subscription: {response.message}")
    
    def reactivate_web_subscription(self) -> ReactivateWebSubscriptionResponse:
        """
        Reactivate the user's web subscription
        
        API Endpoint: POST /subscription/web/reactivate
        
        Returns:
            ReactivateWebSubscriptionResponse: Pydantic model with success status
        
        Note: Requires authentication token to be set
        
        Example:
            >>> mlm = MlmAPI()
            >>> mlm.login("test@example.com", "Aa123456")
            >>> result = mlm.reactivate_web_subscription()
            >>> if result.success:
            ...     print("Subscription reactivated successfully")
        """
        endpoint = "/subscription/web/reactivate"
        
        self.logger.info("Reactivating web subscription")
        response = self.post(endpoint, json_data={})
        
        if response.is_success():
            # Parse response into Pydantic model
            reactivate_data = ReactivateWebSubscriptionResponse(**response.json_data)
            self.logger.info("Web subscription reactivated successfully")
            return reactivate_data
        else:
            raise Exception(f"Failed to reactivate web subscription: {response.message}")
    
    def get_ag_license(self) -> GetAGLicenseResponse:
        """
        Get Awesome Golf license information for the authenticated user
        
        API Endpoint: GET /subscription/awesome-golf/license
        
        Returns:
            GetAGLicenseResponse: Pydantic model containing license details
        
        Note: Requires authentication token to be set
        
        Example:
            >>> mlm = MlmAPI()
            >>> mlm.login("test@example.com", "Aa123456")
            >>> license_data = mlm.get_ag_license()
            >>> 
            >>> if license_data.is_valid():
            ...     info = license_data.get_license_info()
            ...     print(f"License ID: {info['license_id']}")
            ...     print(f"Duration: {info['duration_months']} months")
            ...     print(f"Expires: {info['expire_date']}")
        """
        endpoint = "/subscription/awesome-golf/license"
        
        self.logger.info("Getting Awesome Golf license")
        response = self.get(endpoint)
        
        if response.is_success():
            # Parse response into Pydantic model
            license_data = GetAGLicenseResponse(**response.json_data)
            self.logger.info(f"AG License retrieved - ID: {license_data.license.id}, Duration: {license_data.license.duration} months")
            return license_data
        else:
            raise Exception(f"Failed to get AG license: {response.message}")
    
    def delete_user_account(self) -> APIResponse:
        """
        Delete the currently authenticated user's account
        
        API Endpoint: DELETE /user
        
        Returns:
            APIResponse: Response from the delete operation
        
        Note: Requires authentication token to be set
        
        Example:
            >>> mlm = MlmAPI()
            >>> mlm.login("test@example.com", "Aa123456")
            >>> delete_response = mlm.delete_user_account()
            >>> if delete_response.is_success():
            ...     print("User account deleted successfully")
        """
        endpoint = "/user"
        
        self.logger.info("Deleting user account")
        response = self.delete(endpoint)
        
        if response.is_success():
            self.logger.info("User account deleted successfully")
        else:
            self.logger.warning(f"Failed to delete user account: {response.message}")
        
        return response
    
