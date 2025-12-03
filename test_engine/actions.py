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
    
    def execute_action(
        self, 
        action_name: str, 
        param: Optional[str] = None,
        subscription_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a single action
        
        Args:
            action_name: Action identifier (e.g., 'purchase_1y_premium')
            param: Action parameter (e.g., 'visa_success')
            subscription_state: Current subscription state (for advance_time calculations)
            
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
        
        # Note: Actions that change subscription type (purchase, upgrade, downgrade) 
        # MUST return 'subscription_type' in their result dict so the executor can 
        # track the latest active subscription across multiple actions
        if action_type == 'purchase':
            return self._execute_purchase_action(action_name, action_config, param)
        elif action_type == 'cancel':
            return self._execute_cancel_action(action_name, action_config)
        elif action_type == 'reactivate':
            return self._execute_reactivate_action(action_name, action_config)
        elif action_type == 'advance_time':
            return self._execute_advance_time_action(action_name, action_config, param, subscription_state)
        elif action_type == 'verify':
            return self._execute_verify_action(action_name, action_config, param)
        # TODO: Implement upgrade, downgrade actions (must return subscription_type)
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
    
    def _execute_cancel_action(self, action_name: str, action_config: Dict) -> Dict[str, Any]:
        """
        Execute a cancel subscription action
        
        Args:
            action_name: Action name
            action_config: Action configuration
            
        Returns:
            Result dictionary
        """
        self.logger.info(f"Executing cancel action: {action_name}")
        
        try:
            # Call the MLM API to cancel subscription
            self.logger.info("Calling MLM API to cancel web subscription...")
            cancel_response = self.mlm_api.cancel_web_subscription()
            
            if cancel_response.success:
                self.logger.info("✓ Subscription cancelled successfully")
                return {
                    'success': True,
                    'message': 'Subscription cancelled successfully',
                    'action': action_name,
                    'api_response': {
                        'success': cancel_response.success
                    }
                }
            else:
                self.logger.error("✗ Subscription cancellation failed")
                return {
                    'success': False,
                    'message': 'Subscription cancellation failed',
                    'api_response': {
                        'success': cancel_response.success
                    }
                }
        
        except Exception as e:
            self.logger.error(f"Error executing cancel action: {str(e)}")
            return {
                'success': False,
                'message': f'Exception during cancel: {str(e)}',
                'error': str(e)
            }
    
    def _execute_reactivate_action(self, action_name: str, action_config: Dict) -> Dict[str, Any]:
        """
        Execute a reactivate subscription action
        
        Args:
            action_name: Action name
            action_config: Action configuration
            
        Returns:
            Result dictionary
        """
        self.logger.info(f"Executing reactivate action: {action_name}")
        
        try:
            # Call the MLM API to reactivate subscription
            self.logger.info("Calling MLM API to reactivate web subscription...")
            reactivate_response = self.mlm_api.reactivate_web_subscription()
            
            if reactivate_response.success:
                self.logger.info("✓ Subscription reactivated successfully")
                return {
                    'success': True,
                    'message': 'Subscription reactivated successfully',
                    'action': action_name,
                    'api_response': {
                        'success': reactivate_response.success
                    }
                }
            else:
                self.logger.error("✗ Subscription reactivation failed")
                return {
                    'success': False,
                    'message': 'Subscription reactivation failed',
                    'api_response': {
                        'success': reactivate_response.success
                    }
                }
        
        except Exception as e:
            self.logger.error(f"Error executing reactivate action: {str(e)}")
            return {
                'success': False,
                'message': f'Exception during reactivate: {str(e)}',
                'error': str(e)
            }
    
    def _execute_advance_time_action(
        self, 
        action_name: str, 
        action_config: Dict, 
        param: Optional[str],
        subscription_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute time advancement action (MANUAL INTERVENTION REQUIRED)
        
        This action pauses the framework and waits for the tester to manually advance time
        in Stripe Dashboard, then confirm the advancement.
        
        Args:
            action_name: Action name
            action_config: Action configuration
            param: Number of days to advance (as string)
            subscription_state: Current subscription state with days_advanced tracking
            
        Returns:
            Result dictionary
        """
        from datetime import datetime, timedelta
        
        self.logger.info(f"Executing advance_time action: {action_name}")
        
        try:
            # Parse days parameter
            if not param:
                raise ValueError("advance_time requires 'days' parameter (e.g., 46)")
            
            try:
                days_to_advance = int(param)
            except ValueError:
                raise ValueError(f"advance_time parameter must be an integer (days), got: {param}")
            
            if days_to_advance <= 0:
                raise ValueError(f"advance_time days must be positive, got: {days_to_advance}")
            
            self.logger.info(f"Requested time advancement: {days_to_advance} days")
            
            # Get user information for instructions
            user_data = self.mlm_api.get_user_data()
            user_email = user_data.get('email', 'N/A')
            
            # Calculate simulated current date and target date
            # Use the subscription start date + previously advanced days
            subscriptions = self.mlm_api.get_subscriptions()
            if subscriptions.subscriptions:
                # Get the FIRST (original) subscription's start date
                # Note: API returns newest first, so the last one is the original
                original_sub = subscriptions.subscriptions[-1]
                start_date = datetime.fromisoformat(original_sub.startDate.replace('Z', '+00:00'))
                
                # Get previously advanced days from subscription_state
                days_already_advanced = subscription_state.get('days_advanced', 0) if subscription_state else 0
                
                # Calculate simulated current date
                simulated_current = start_date + timedelta(days=days_already_advanced)
                
                # Calculate target date in UTC
                target_date_utc = simulated_current + timedelta(days=days_to_advance)
                
                # Convert to Singapore time (GMT+8) for display
                target_date_sg = target_date_utc + timedelta(hours=8)
                target_date_str = target_date_sg.strftime("%b %d, %Y at %H:%M")
                
                self.logger.info(f"Original start date: {start_date}")
                self.logger.info(f"Days already advanced: {days_already_advanced}")
                self.logger.info(f"Simulated current date: {simulated_current}")
                self.logger.info(f"Target date UTC (+ {days_to_advance} days): {target_date_utc}")
                self.logger.info(f"Target date Singapore (GMT+8): {target_date_sg}")
            else:
                target_date_str = f"{days_to_advance} days from current simulated time"
            
            # Display manual intervention instructions
            print("\n" + "=" * 80)
            print("⏰ MANUAL TIME ADVANCEMENT REQUIRED")
            print("=" * 80)
            print(f"User Email: {user_email}")
            print(f"Days to Advance: {days_to_advance} days")
            print("\nINSTRUCTIONS:")
            print("1. Open Stripe Dashboard (Test Mode)")
            print(f"2. Search for customer email: {user_email}")
            print("3. Click on the customer's active subscription")
            print("4. Click 'Run simulation' button")
            print(f"5. Enter the exact date and time: {target_date_str} (GMT+8)")
            print("6. Click 'Advance time' button in Stripe")
            print("7. Verify the time was advanced successfully")
            print("8. Return here and press ENTER to continue")
            print("=" * 80)
            
            # Wait for user confirmation
            input("\nPress ENTER after you have manually advanced time in Stripe Dashboard...")
            
            # Ask for actual days advanced (in case tester advanced different amount)
            while True:
                actual_days_input = input(f"How many days did you actually advance? [{days_to_advance}]: ").strip()
                if not actual_days_input:
                    actual_days_advanced = days_to_advance
                    break
                try:
                    actual_days_advanced = int(actual_days_input)
                    if actual_days_advanced > 0:
                        break
                    else:
                        print("Please enter a positive number of days")
                except ValueError:
                    print("Please enter a valid integer")
            
            self.logger.info(f"✓ Time advanced: {actual_days_advanced} days (requested: {days_to_advance})")
            
            if actual_days_advanced != days_to_advance:
                self.logger.warning(f"⚠ Actual days ({actual_days_advanced}) differs from requested ({days_to_advance})")
            
            return {
                'success': True,
                'message': f'Time advanced by {actual_days_advanced} days (manual)',
                'action': action_name,
                'days_requested': days_to_advance,
                'days_advanced': actual_days_advanced
            }
        
        except Exception as e:
            self.logger.error(f"Error executing advance_time action: {str(e)}")
            return {
                'success': False,
                'message': f'Exception during advance_time: {str(e)}',
                'error': str(e)
            }

    def _execute_verify_action(self, action_name: str, action_config: Dict[str, Any], param: str = None) -> Dict[str, Any]:
        """
        Execute manual verification step - pause and wait for tester input

        This method follows the same pattern as other action executors:
        - Takes action_name, action_config, and param
        - Returns dict with success and details

        Args:
            action_name: Name of the action (verify)
            action_config: Action configuration from actions.json
            param: Hint text to show the tester about what to verify

        Returns:
            Dict containing verification results with keys:
                - success: bool (whether manual verification passed)
                - hint: str (the hint shown to tester)
                - result: str ('passed' or 'failed')
                - notes: str (detailed notes from tester)
                - timestamp: str (when verification was performed)
                - action_type: str ('verification') - for routing in executor
        """
        from datetime import datetime

        self.logger.info("=" * 80)
        self.logger.info("🔍 MANUAL VERIFICATION REQUIRED")
        self.logger.info("=" * 80)

        # Get user information
        user_data = self.mlm_api.get_user_data()
        user_email = user_data.get('email', 'N/A')

        # Show user info and the hint
        print(f"\n👤 USER INFO:")
        print(f"   Email: {user_email}")

        # Show the hint
        hint_text = param if param else "Verify the expected behavior manually"
        print(f"\n📌 VERIFICATION HINT:")
        print(f"   {hint_text}")
        print("\n" + "-" * 80)

        # Wait for pass/fail input
        while True:
            print("\n⏸️  Please perform the manual verification step.")
            print("   After verification, enter:")
            print("   - 'p' or 'pass' if the step PASSED ✓")
            print("   - 'f' or 'fail' if the step FAILED ✗")
            print()

            result_input = input("   Enter result (p/f): ").strip().lower()

            if result_input in ['p', 'pass', 'passed']:
                result = 'passed'
                success = True
                print("\n   ✓ Verification marked as PASSED")
                break
            elif result_input in ['f', 'fail', 'failed']:
                result = 'failed'
                success = False
                print("\n   ✗ Verification marked as FAILED")
                break
            else:
                print(f"   ⚠️  Invalid input: '{result_input}'. Please enter 'p' or 'f'")

        # Get detailed notes
        print("\n" + "-" * 80)
        print("📝 Please provide detailed notes about this verification step:")
        print("   (What was verified? What was the result? Any issues?)")
        print("   Press ENTER on an empty line when done.")
        print()

        notes_lines = []
        while True:
            line = input("   ")
            if line.strip() == "":
                break
            notes_lines.append(line)

        notes = "\n".join(notes_lines) if notes_lines else "No additional notes provided"

        # Log the results
        timestamp = datetime.now().isoformat()
        self.logger.info(f"Manual verification completed: {result.upper()}")
        self.logger.info(f"Notes: {notes}")

        print("\n" + "=" * 80)
        print(f"✓ Manual verification step recorded")
        print("=" * 80 + "\n")

        return {
            'success': success,
            'hint': hint_text,
            'result': result,
            'notes': notes,
            'timestamp': timestamp,
            'action_type': 'verify'
        }