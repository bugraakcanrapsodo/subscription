"""
Action Executor
Executes test actions based on configuration
"""

import json
import requests
from typing import Dict, Any, Optional
from pathlib import Path
from base.logger import Logger
from api.mlm_api import MlmAPI
from test_engine.stripe_verifier import StripeCheckoutVerifier


class ActionExecutor:
    """
    Execute test actions based on actions.json configuration
    """
    
    def __init__(
        self,
        mlm_api: MlmAPI,
        playwright_service_url: str = "http://localhost:3001",
        currency: str = 'usd',
        country_code: str = 'us',
        trial_eligible: bool = True
    ):
        """
        Initialize action executor
        
        Args:
            mlm_api: MLM API client instance
            playwright_service_url: URL of the Playwright service
            currency: Currency code for transactions (auto-determined from country)
            country_code: Country code (e.g., 'us', 'ca', 'de')
            trial_eligible: Whether user is trial eligible
        """
        self.mlm_api = mlm_api
        self.playwright_service_url = playwright_service_url
        self.currency = currency.lower()
        self.country_code = country_code.lower()
        self.trial_eligible = trial_eligible
        self.logger = Logger(__name__)
        
        # Initialize Stripe checkout verifier
        self.stripe_verifier = StripeCheckoutVerifier(playwright_service_url)
        
        # Load action configurations
        config_path = Path(__file__).parent.parent / 'config' / 'actions.json'
        with open(config_path, 'r') as f:
            self.actions_config = json.load(f)
        
        # Load subscription configurations
        subscriptions_path = Path(__file__).parent.parent / 'config' / 'subscriptions.json'
        with open(subscriptions_path, 'r') as f:
            self.subscriptions_config = json.load(f)
        
        # Load test cards configuration
        test_cards_path = Path(__file__).parent.parent / 'config' / 'test_cards.json'
        with open(test_cards_path, 'r') as f:
            self.test_cards_config = json.load(f)
        
        self.logger.info(f"Loaded {len(self.actions_config)} action(s) from configuration")
        self.logger.info(f"Loaded {len(self.test_cards_config)} test card(s) from configuration")
    
    def execute_action(self, action_name: str, param: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a single action
        
        Args:
            action_name: Action identifier (e.g., 'purchase_1y_premium')
            param: Action parameter (e.g., 'visa_success')
            
        Returns:
            Result dictionary with status and details
        """
        self.logger.info(f"Executing action: {action_name} (param: {param})")
        
        # Validate action exists
        if action_name not in self.actions_config:
            raise ValueError(f"Unknown action: {action_name}. Available: {list(self.actions_config.keys())}")
        
        action_config = self.actions_config[action_name]
        
        # Route to appropriate handler based on action type
        action_type = action_config.get('action_type')
        
        if action_type == 'purchase':
            return self._execute_purchase_action(action_name, action_config, param)
        else:
            raise NotImplementedError(f"Action type not implemented: {action_type}")
    
    def _execute_purchase_action(self, action_name: str, action_config: Dict, param: Optional[str]) -> Dict[str, Any]:
        """
        Execute a purchase action
        
        Args:
            action_name: Action name
            action_config: Action configuration
            param: Card type parameter
            
        Returns:
            Result dictionary
        """
        self.logger.info(f"Executing purchase action: {action_name}")
        
        # Get subscription details
        subscription_type = action_config.get('subscription_type')
        subscription_config = self.subscriptions_config.get(subscription_type)
        
        if not subscription_config:
            raise ValueError(f"Subscription type not found: {subscription_type}")
        
        plan_code = subscription_config['code']
        supports_trial = subscription_config.get('supports_trial', False)
        trial_period_days = subscription_config.get('trial_period_days', 0)
        
        self.logger.info(f"Subscription: {subscription_config['description']}")
        self.logger.info(f"Plan code: {plan_code}")
        if supports_trial:
            self.logger.info(f"Trial period: {trial_period_days} days (if user is trial eligible)")
        
        # Get card details based on parameter
        card_type = param or action_config['parameters']['card_type']['default']
        
        if card_type not in self.test_cards_config:
            raise ValueError(f"Unknown card type: {card_type}. Available: {list(self.test_cards_config.keys())}")
        
        card_details = self.test_cards_config[card_type]
        expected_result = card_details['expected_result']
        
        self.logger.info(f"Using card: {card_type} (expected: {expected_result})")
        
        try:
            # Step 1: Get web plans to verify eligibility
            self.logger.info("Step 1: Getting web plans...")
            plans_response = self.mlm_api.get_web_plans(country="us")
            eligible_plans = plans_response.get_eligible_plans()
            
            self.logger.info(f"Eligible plans: {[p['name'] for p in eligible_plans]}")
            
            # Verify plan is eligible
            plan_eligible = any(p['code'] == plan_code for p in eligible_plans)
            if not plan_eligible:
                return {
                    'success': False,
                    'message': f'Plan {subscription_type} (code: {plan_code}) is not eligible',
                    'eligible_plans': eligible_plans
                }
            
            # Step 2: Create web subscription to get checkout URL
            self.logger.info(f"Step 2: Creating subscription with plan code: {plan_code}")
            subscription_response = self.mlm_api.create_web_subscription(plan_code=plan_code)
            checkout_url = subscription_response.get_checkout_url()
            
            if not checkout_url:
                return {
                    'success': False,
                    'message': 'Failed to get checkout URL from subscription creation'
                }
            
            self.logger.info(f"Checkout URL: {checkout_url}")
            
            # Step 3: Verify checkout page shows correct price
            self.logger.info(f"Step 3: Verifying Stripe checkout page price in {self.currency.upper()}...")
            
            checkout_verification = self.stripe_verifier.verify_checkout_page_gui(
                checkout_url=checkout_url,
                subscription_type=subscription_type,
                currency=self.currency,
                trial_eligible=self.trial_eligible,
                country=self.country_code
            )
            
            if not checkout_verification.get('verified'):
                self.logger.error(f"Checkout verification failed: {checkout_verification.get('message')}")
                return {
                    'success': False,
                    'message': f"Checkout price verification failed: {checkout_verification.get('message')}",
                    'checkout_verification': checkout_verification
                }
            
            self.logger.info(f"✓ Checkout page verified: {checkout_verification.get('message')}")
            
            # Step 4: Complete payment via Playwright service
            self.logger.info("Step 4: Completing payment via Playwright service...")
            
            # Get auth token and user data for Local Storage
            try:
                auth_token = self.mlm_api.get_auth_token()
                user_data = self.mlm_api.get_user_data()
            except ValueError as e:
                self.logger.error(f"Failed to get auth token or user data: {e}")
                return {
                    'success': False,
                    'message': f"Missing auth credentials: {str(e)}"
                }
            
            payment_result = self._complete_payment_via_playwright(
                checkout_url=checkout_url,
                card_details=card_details,
                currency=self.currency,
                auth_token=auth_token,
                user_data=user_data,
                country=self.country_code
            )
            
            if expected_result == 'success':
                if payment_result['success']:
                    self.logger.info("✓ Payment completed successfully as expected")
                    return {
                        'success': True,
                        'message': 'Purchase completed successfully',
                        'subscription_type': subscription_type,
                        'plan_code': plan_code,
                        'card_type': card_type,
                        'currency': self.currency,
                        'checkout_verification': checkout_verification,
                        'payment_result': payment_result
                    }
                else:
                    self.logger.error("✗ Payment failed but success was expected")
                    return {
                        'success': False,
                        'message': 'Payment failed unexpectedly',
                        'expected': 'success',
                        'actual': 'failed',
                        'payment_result': payment_result
                    }
            else:
                # Expected failure (declined card)
                if not payment_result['success']:
                    self.logger.info(f"✓ Payment failed as expected ({expected_result})")
                    return {
                        'success': True,
                        'message': f'Payment correctly declined ({expected_result})',
                        'expected_result': expected_result,
                        'payment_result': payment_result
                    }
                else:
                    self.logger.error("✗ Payment succeeded but failure was expected")
                    return {
                        'success': False,
                        'message': 'Payment succeeded unexpectedly',
                        'expected': expected_result,
                        'actual': 'success',
                        'payment_result': payment_result
                    }
        
        except Exception as e:
            self.logger.error(f"Error executing purchase action: {str(e)}")
            return {
                'success': False,
                'message': f'Exception during purchase: {str(e)}',
                'error': str(e)
            }
    
    def _complete_payment_via_playwright(
        self,
        checkout_url: str,
        card_details: Dict,
        currency: str = 'usd',
        auth_token: Optional[str] = None,
        user_data: Optional[Dict] = None,
        country: str = 'us'
    ) -> Dict[str, Any]:
        """
        Complete payment via Playwright service
        
        Args:
            checkout_url: Stripe checkout URL
            card_details: Card details dictionary
            currency: Currency code (e.g., 'usd', 'jpy')
            auth_token: MLM auth token (for Local Storage)
            user_data: User data (for Local Storage)
            country: Country code for VPN connection (e.g., 'us', 'jp')
            
        Returns:
            Result dictionary with success status
        """
        try:
            # Call Playwright service
            payload = {
                'checkoutUrl': checkout_url,
                'currency': currency.upper(),
                'country': country.lower(),
                'cardNumber': card_details['card_number'],
                'cardExpiry': card_details['card_expiry'],
                'cardCvc': card_details['card_cvc'],
                'cardholderName': card_details['cardholder_name'],
                'authToken': auth_token,
                'userData': user_data
            }
            
            self.logger.info(f"Calling Playwright service at: {self.playwright_service_url}")
            self.logger.info(f"  VPN Country: {country.upper()}, Currency: {currency.upper()}")
            
            response = requests.post(
                f'{self.playwright_service_url}/api/checkout/pay-card',
                json=payload,
                timeout=120  # 2 minute timeout for checkout process
            )
            
            # Log full response from Docker Playwright service
            self.logger.info(f"Playwright Service Response (checkout/pay-card):")
            self.logger.info(f"  Status Code: {response.status_code}")
            self.logger.debug(f"  Full Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                payment_succeeded = result.get('data', {}).get('paymentSucceeded', False)
                
                self.logger.info(f"  Success: {result.get('success')}")
                self.logger.info(f"  Message: {result.get('message')}")
                self.logger.info(f"  Payment Succeeded: {payment_succeeded}")
                
                # Log VPN location verification if available
                vpn_verification = result.get('vpnLocationVerification')
                if vpn_verification:
                    self.logger.info(f"VPN Location Verification:")
                    if vpn_verification.get('success'):
                        self.logger.info(f"  ✓ Verified: External IP is from {vpn_verification.get('detectedCountry', 'unknown').upper()}")
                        self.logger.info(f"  IP: {vpn_verification.get('ip', 'N/A')}, City: {vpn_verification.get('city', 'N/A')}, {vpn_verification.get('region', 'N/A')}")
                    else:
                        self.logger.warning(f"  ✗ Location Mismatch: Expected {vpn_verification.get('expectedCountry', 'unknown').upper()}, Got {vpn_verification.get('detectedCountry', 'unknown').upper()}")
                        self.logger.warning(f"  IP: {vpn_verification.get('ip', 'N/A')}, City: {vpn_verification.get('city', 'N/A')}")
                        self.logger.warning(f"  This may cause currency/pricing mismatches!")
                
                return {
                    'success': payment_succeeded,
                    'playwright_response': result,
                    'screenshots': {
                        'before': result.get('data', {}).get('beforeScreenshot'),
                        'after': result.get('data', {}).get('afterScreenshot')
                    }
                }
            else:
                self.logger.error(f"Playwright service returned non-200 status: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return {
                    'success': False,
                    'error': f'Playwright service returned {response.status_code}',
                    'response': response.text
                }
        
        except requests.exceptions.Timeout:
            self.logger.error("Playwright service timeout")
            return {
                'success': False,
                'error': 'Timeout waiting for Playwright service'
            }
        except Exception as e:
            self.logger.error(f"Error calling Playwright service: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

