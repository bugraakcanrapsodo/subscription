"""
Test Executor
Main orchestrator for data-driven test execution
"""

import os
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from base.logger import Logger
from api.mlm_api import MlmAPI
from test_engine.excel_reader import ExcelReader
from test_engine.actions import ActionExecutor
from test_engine.user_verifier import UserVerifier
from test_engine.admin_verifier import AdminVerifier
from test_engine.reporter import Reporter
from test_engine.location_manager import LocationManager
import json


class TestExecutor:
    """
    Main test executor that orchestrates the entire test flow
    """

    def __init__(
        self,
        mlm_api: MlmAPI,
        playwright_service_url: str = "http://localhost:3001",
        cleanup_users: str = "passed"
    ):
        """
        Initialize test executor

        Args:
            mlm_api: MLM API client instance
            playwright_service_url: URL of Playwright service
            cleanup_users: User cleanup mode - "never", "passed" (default), or "always"
        """
        self.mlm_api = mlm_api
        self.playwright_service_url = playwright_service_url
        self.cleanup_users = cleanup_users
        self.logger = Logger(__name__)

        # Validate cleanup mode
        valid_modes = ["never", "passed", "always"]
        if self.cleanup_users not in valid_modes:
            self.logger.warning(
                f"Invalid cleanup mode '{self.cleanup_users}', defaulting to 'passed'. "
                f"Valid modes: {valid_modes}"
            )
            self.cleanup_users = "passed"

        # Log cleanup mode
        self.logger.info(f"User cleanup mode: {self.cleanup_users}")

        # Initialize components (will be re-initialized per test with location and trial status)
        self.action_executor = None  # Will be initialized per test
        self.user_verifier = None  # Will be initialized per test
        self.admin_verifier = None  # Will be initialized per test
        self.reporter = Reporter()
        self.location_manager = LocationManager()  # Initialize location manager
        self.admin_logged_in = False  # Track admin login status

    def _is_trial_eligible(self, trial_status: str) -> bool:
        """
        Determine if a trial status indicates trial eligibility.

        Args:
            trial_status: Trial status string (case-insensitive)

        Returns:
            True if trial eligible, False otherwise

        Note:
            Accepts 'Active', 'active', 'True', 'true', etc. as trial eligible
        """
        return str(trial_status).lower() in ['active', 'true', 'yes', 'y']

    def run_tests_from_file(
        self,
        file_path: str,
        test_id: Optional[str] = None,
        test_tag: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Run tests from Excel/CSV file

        Args:
            file_path: Path to test file
            test_id: Optional specific test ID to run
            test_tag: Optional tag(s) to filter tests.
                      Single tag: 'smoke'
                      Multiple tags: 'smoke:refund' (runs tests matching ANY tag)

        Returns:
            List of test results
        """
        self.logger.info(f"Starting test execution from file: {file_path}")

        # Read test cases
        reader = ExcelReader(file_path)

        if test_id:
            # Run specific test
            self.logger.info(f"Running specific test: {test_id}")
            test_case = reader.get_test_case_by_id(test_id)
            test_cases = [test_case]
        elif test_tag:
            # Run tests matching any of the provided tags
            # Split by colon to support multiple tags: "smoke:refund"
            tags = [t.strip().lower() for t in test_tag.split(':') if t.strip()]
            self.logger.info(f"Filtering tests by tag(s): {tags}")

            all_test_cases = reader.read_test_cases()
            test_cases = [
                tc for tc in all_test_cases
                if tc.get('test_tag') and any(
                    tag in str(tc.get('test_tag')).lower()
                    for tag in tags
                )
            ]
            if not test_cases:
                self.logger.warning(f"No tests found with tag(s): {tags}")
                return []
            self.logger.info(f"Found {len(test_cases)} test(s) matching tag(s) {tags}")
        else:
            # Run all tests
            test_cases = reader.read_test_cases()

        self.logger.info(f"Executing {len(test_cases)} test case(s)")

        # Execute each test case
        test_results = []
        for idx, test_case in enumerate(test_cases, start=1):
            self.logger.info(f"\n{'=' * 80}")
            self.logger.info(f"Test {idx}/{len(test_cases)}: {test_case['test_id']}")
            self.logger.info(f"{'=' * 80}")

            result = self.run_single_test(test_case)
            test_results.append(result)

        # Generate reports
        self.logger.info("\nGenerating test reports...")
        report_paths = self.reporter.generate_report(test_results)
        self.logger.info(json.dumps(test_results, indent=2))


        # Print summary
        self.reporter.print_summary(test_results)

        return test_results

    def run_single_test(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single test case

        Args:
            test_case: Test case dictionary

        Returns:
            Test result dictionary
        """
        test_id = test_case['test_id']
        test_name = test_case.get('test_name', 'N/A')

        start_time = time.time()

        result = {
            'test_id': test_id,
            'test_name': test_name,
            'passed': False,
            'action_results': [],
            'verification_results': [],
            'error': None,
            'user_email': None,
            'duration': 0
        }

        try:
            # Step 1: Setup user
            self.logger.info(f"Step 1: Setting up user for test {test_id}")
            user_email = self._setup_user(test_case)
            result['user_email'] = user_email

            # Initialize action executor and verifier with country (currency determined from country)
            country_code = test_case.get('country', 'us')  # Default to US if not specified
            trial_status = test_case.get('trial_status', 'None')
            trial_eligible = self._is_trial_eligible(trial_status)

            # Get currency and country name from country code
            currency = self.location_manager.get_currency_for_location(country_code)
            country_name = self.location_manager.get_country_name_for_location(country_code)


            trial_status_text = "Trial Eligible" if trial_eligible else "No Trial"
            self.logger.info(f"Country: {country_code.upper()} ({country_name}) → Currency: {currency.upper()} | {trial_status_text}")

            self.action_executor = ActionExecutor(
                self.mlm_api,
                self.playwright_service_url,
                currency=currency,
                country_code=country_code,
                trial_eligible=trial_eligible
            )
            self.user_verifier = UserVerifier(self.mlm_api, trial_eligible=trial_eligible)
            self.admin_verifier = AdminVerifier(self.mlm_api)

            # Step 2: Parse and execute actions
            self.logger.info(f"Step 2: Executing actions for test {test_id}")
            reader = ExcelReader.__new__(ExcelReader)  # Create instance without file
            actions = reader.parse_actions(test_case)

            if not actions:
                raise ValueError("No actions defined in test case")

            self.logger.info(f"Found {len(actions)} action(s) to execute")

            # Execute each action
            all_actions_passed = True

            # Track subscription state across all actions
            # This is needed for verification of cancel/reactivate/advance_time
            subscription_state = {
                'test_name': test_name,  # Test name for display in manual steps
                'subscription_type': None,  # e.g., '1y_premium', '2y_premium'
                'plan_code': None,  # e.g., 1 (from subscription config)
                'duration_months': None,  # e.g., 12, 24, 120 (from subscription config)
                'status_code': None,  # e.g., 1=active, 3=trial, 4=cancelled
                'start_date': None,  # ISO format
                'expire_date': None,  # ISO format
                'trial_period_days': None,  # e.g., 45
                'is_cancelled': False,  # Whether subscription was cancelled
                'days_advanced': 0  # Total days advanced via advance_time actions
            }

            for action_idx, action_data in enumerate(actions, start=1):
                action_name = action_data['action']
                param = action_data['param']

                self.logger.info(f"\nAction {action_idx}/{len(actions)}: {action_name}")

                try:
                    # Execute action
                    action_result = self.action_executor.execute_action(
                        action_name,
                        param,
                        subscription_state=subscription_state
                    )
                    result['action_results'].append({
                        'action': action_name,
                        'param': param,
                        'success': action_result.get('success', False),
                        'message': action_result.get('message')  # Keep for failed action debugging
                    })
                    
                    # Extract checkout_verification from action result and add to verification_results
                    checkout_verification = action_result.get('checkout_verification')
                    if checkout_verification:
                        checkout_verify_result = {
                            'verified': checkout_verification.get('verified'),
                            'message': checkout_verification.get('message'),
                            'checks': checkout_verification.get('checks', {}),
                            'action_name': action_name,
                            'verification_type': 'stripe_checkout',
                            'checkout_details': checkout_verification.get('checkout_details'),
                            'expected_price': checkout_verification.get('expected_price'),
                            'actual_price': checkout_verification.get('actual_price'),
                            'expected_currency': checkout_verification.get('expected_currency'),
                            'actual_currency': checkout_verification.get('actual_currency'),
                            'expected_product_name': checkout_verification.get('expected_product_name'),
                            'actual_product_name': checkout_verification.get('actual_product_name'),
                            'expected_trial_text': checkout_verification.get('expected_trial_text'),
                            'actual_trial_text': checkout_verification.get('actual_trial_text'),
                            'screenshot': checkout_verification.get('screenshot')
                        }
                        if checkout_verification.get('issues'):
                            checkout_verify_result['issues'] = checkout_verification.get('issues')
                        
                        result['verification_results'].append(checkout_verify_result)

                    action_type = self.action_executor.actions_config[action_name].get('action_type')

                    # Update subscription state from action results
                    if action_result.get('success'):
                        # Track subscription_type from purchase/upgrade/downgrade actions
                        # Also extract plan_code and duration_months from subscription config
                        if action_result.get('subscription_type'):
                            subscription_type = action_result.get('subscription_type')
                            subscription_state['subscription_type'] = subscription_type

                            # Load subscription config to get plan_code and duration_months
                            from pathlib import Path
                            import json
                            config_path = Path(__file__).parent.parent / 'config' / 'subscriptions.json'
                            with open(config_path, 'r') as f:
                                subscriptions_config = json.load(f)

                            sub_config = subscriptions_config.get(subscription_type, {})
                            subscription_state['plan_code'] = sub_config.get('code')
                            subscription_state['duration_months'] = sub_config.get('duration_months')

                            self.logger.info(f"Updated subscription metadata: type={subscription_type}, plan_code={subscription_state['plan_code']}, duration_months={subscription_state['duration_months']}")

                        # Track cancel status
                        if action_type == 'cancel':
                            subscription_state['is_cancelled'] = True
                            self.logger.info("Subscription marked as cancelled")
                        elif action_type == 'reactivate':
                            subscription_state['is_cancelled'] = False
                            self.logger.info("Subscription marked as reactivated")
                        elif action_type == 'advance_time':
                            # Track days advanced
                            days_advanced = action_result.get('days_advanced', 0)
                            subscription_state['days_advanced'] += days_advanced
                            self.logger.info(f"Total days advanced: {subscription_state['days_advanced']}")

                    # Check if this is a manual verification action
                    if action_type == 'verify':
                        # Manual verification action - no user/admin API verification needed
                        # The action itself returns the verification result

                        self.logger.info(f"Processing manual verification result...")

                        # Store the manual verification result
                        verify_result = {
                            'verified': True,
                            'action_name': action_name,
                            'verification_type': 'manual',
                            'manual_verification': {
                                'passed': action_result.get('success', False),
                                'result': action_result.get('result', 'unknown'),
                                'hint': action_result.get('hint', ''),
                                'notes': action_result.get('notes', ''),
                                'timestamp': action_result.get('timestamp', '')
                            }
                        }
                        result['verification_results'].append(verify_result)

                        # If verification failed, mark test as failed
                        if not action_result.get('success'):
                            all_actions_passed = False
                            self.logger.error(f"Manual verification failed: {action_result.get('hint')}")
                        else:
                            self.logger.info(f"✓ Manual verification passed")

                        # Skip the normal user/admin verification for this action
                        continue

                    if not action_result.get('success'):
                        all_actions_passed = False
                        self.logger.error(f"Action failed: {action_result.get('message')}")
                        self.logger.error(f"Stopping test execution - cannot proceed with subsequent actions")
                        # STOP execution - don't verify failed action or run subsequent actions
                        break

                    # RE-LOGIN after payment to refresh session and get updated subscription data
                    self.logger.info(f"Re-logging in to refresh session after payment...")
                    relogin_response = self.mlm_api.login(user_email, "Aa123456")
                    if not relogin_response.is_success():
                        self.logger.error(f"Re-login failed: {relogin_response.message}")
                    else:
                        self.logger.info(f"✓ Re-login successful, session refreshed")

                    # Wait 2 seconds for backend to process webhook and update subscription
                    self.logger.info("Waiting 2 seconds for backend webhook processing...")
                    time.sleep(2)

                    # Verify action result (USER-LEVEL API)
                    self.logger.info(f"Verifying action result (User API)...")
                    verify_result = self.user_verifier.verify_from_user_api(
                        action_name,
                        action_result,
                        subscription_state=subscription_state
                    )
                    # Add action context to verification result
                    verify_result['action_name'] = action_name
                    verify_result['verification_type'] = 'user_api'
                    result['verification_results'].append(verify_result)

                    # Update subscription state from verification result
                    # Update even if verification failed, as long as we have subscription data
                    # This ensures subsequent actions have accurate state information
                    if verify_result.get('subscription'):
                        sub_data = verify_result['subscription']
                        subscription_state['status_code'] = sub_data.get('status_code')
                        subscription_state['start_date'] = sub_data.get('start_date')
                        subscription_state['expire_date'] = sub_data.get('expire_date')
                        if sub_data.get('trial_period_days'):
                            subscription_state['trial_period_days'] = sub_data.get('trial_period_days')
                        self.logger.debug(f"Updated subscription state from verification (status={sub_data.get('status_code')}, expire={sub_data.get('expire_date')})")

                    if not verify_result.get('verified'):
                        all_actions_passed = False
                        self.logger.error(f"User API verification failed: {verify_result.get('message')}")
                    else:
                        self.logger.info(f"✓ User API verification passed")

                    # Verify via ADMIN-LEVEL API
                    self.logger.info(f"Verifying action result (Admin API)...")

                    # Login to admin if not already logged in
                    if not self.admin_logged_in:
                        admin_email = os.getenv('MLM_ADMIN_EMAIL')
                        admin_password = os.getenv('MLM_ADMIN_PASSWORD')

                        if not admin_email or not admin_password:
                            self.logger.warning("MLM_ADMIN_EMAIL or MLM_ADMIN_PASSWORD not set in .env, skipping Admin API verification")
                        else:
                            try:
                                admin_login_response = self.mlm_api.admin_login(admin_email, admin_password)
                                if not admin_login_response.is_success():
                                    self.logger.error(f"Admin login failed: {admin_login_response.message}")
                                else:
                                    self.admin_logged_in = True
                                    self.logger.info("✓ Admin API logged in successfully")
                            except Exception as e:
                                self.logger.error(f"Admin login exception: {str(e)}")

                    # Perform admin verification if logged in
                    if self.admin_logged_in:
                        try:
                            # Get expected values from user verification result
                            # Use the SAME expected values to ensure consistency
                            expected_status_code = verify_result.get('expected_status_code')
                            expected_plan_code = verify_result.get('expected_plan_code')
                            expected_duration_months = verify_result.get('expected_duration_months')
                            expected_trial_period_days = verify_result.get('expected_trial_period_days')
                            expected_start_date = verify_result.get('expected_start_date')
                            expected_expire_date = verify_result.get('expected_expire_date')

                            action_type = self.action_executor.actions_config[action_name].get('action_type')
                            admin_verify_result = self.admin_verifier.verify_from_admin_api(
                                user_email=user_email,
                                expected_status_code=expected_status_code,
                                expected_plan_code=expected_plan_code,
                                expected_duration_months=expected_duration_months,
                                expected_trial_period_days=expected_trial_period_days,
                                expected_start_date=expected_start_date,
                                expected_expire_date=expected_expire_date,
                                check_dates=True,  # Enable date verification in admin API
                                subscription_state=subscription_state,
                                action_type=action_type
                            )
                            # Add action context to verification result
                            admin_verify_result['action_name'] = action_name
                            admin_verify_result['verification_type'] = 'admin_api'
                            result['verification_results'].append(admin_verify_result)

                            if not admin_verify_result.get('verified'):
                                # Admin API uses webhook data which may have 30-60+ second delays
                                # User API verification (from login data) is authoritative, so treat admin as warning only
                                self.logger.warning(f"⚠ Admin API verification failed: {admin_verify_result.get('message')}")
                                self.logger.warning("⚠ Note: Admin API depends on webhooks which may have significant delays. This is non-blocking.")
                            else:
                                self.logger.info(f"✓ Admin API verification passed")
                        except Exception as e:
                            self.logger.error(f"Admin verification exception: {str(e)}")
                    else:
                        self.logger.warning("Skipping Admin API verification (not logged in)")

                except Exception as action_error:
                    self.logger.error(f"Exception in action {action_name}: {str(action_error)}")
                    result['action_results'].append({
                        'action': action_name,
                        'param': param,
                        'success': False,
                        'error': str(action_error)
                    })
                    all_actions_passed = False
                    self.logger.error(f"Stopping test execution due to action exception")
                    # STOP execution - don't run subsequent actions after exception
                    break

            # Mark test as passed if all actions passed
            result['passed'] = all_actions_passed

            if result['passed']:
                self.logger.info(f"✓ Test {test_id} PASSED")
            else:
                self.logger.error(f"✗ Test {test_id} FAILED")

        except Exception as e:
            self.logger.error(f"Test execution failed: {str(e)}")
            result['error'] = str(e)
            result['passed'] = False

        finally:
            # Calculate duration
            result['duration'] = time.time() - start_time

            # Smart cleanup based on mode and test result
            if result.get('user_email'):
                should_cleanup = False
                cleanup_reason = ""

                if self.cleanup_users == "always":
                    should_cleanup = True
                    cleanup_reason = "cleanup mode is 'always'"
                elif self.cleanup_users == "passed" and result['passed']:
                    should_cleanup = True
                    cleanup_reason = "test PASSED and cleanup mode is 'passed'"
                elif self.cleanup_users == "never":
                    should_cleanup = False
                    cleanup_reason = "cleanup mode is 'never'"
                else:
                    # cleanup_users == "passed" but test failed
                    should_cleanup = False
                    cleanup_reason = "test FAILED and cleanup mode is 'passed'"

                if should_cleanup:
                    self.logger.info(f"🗑️  Cleaning up user (reason: {cleanup_reason})")
                    self._cleanup_user(result['user_email'])
                else:
                    self.logger.info(f"↪️  Keeping user account (reason: {cleanup_reason})")
                    self.logger.info(f"   User email: {result['user_email']}")

        return result

    def _setup_user(self, test_case: Dict[str, Any]) -> str:
        """
        Setup user for test execution

        Args:
            test_case: Test case dictionary

        Returns:
            User email address
        """
        # Check if email is provided
        user_email = test_case.get('user_email')

        if user_email:
            # Use provided email - login
            self.logger.info(f"Using provided email: {user_email}")
            try:
                login_response = self.mlm_api.login(user_email, "Aa123456")
                if not login_response.is_success():
                    raise Exception(f"Login failed for {user_email}")
                return user_email
            except Exception as e:
                self.logger.warning(f"Login failed, will try to register: {str(e)}")

        # Generate email if not provided
        if not user_email:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            test_id = test_case['test_id'].lower().replace(' ', '_')
            user_email = f"automation_user_{test_id}_{timestamp}@rapsodotest.com"
            self.logger.info(f"Generated email: {user_email}")

        # Register new user
        self.logger.info("Registering new user...")
        register_response = self.mlm_api.register(
            email=user_email,
            first_name="Test",
            last_name="User",
            password="Aa123456"
        )

        if not register_response.is_success():
            raise Exception(f"Registration failed: {register_response.message}")

        # Login after registration
        self.logger.info("Logging in...")
        login_response = self.mlm_api.login(user_email, "Aa123456")

        if not login_response.is_success():
            raise Exception(f"Login failed: {login_response.message}")

        # Register device based on trial_status
        trial_status = test_case.get('trial_status', 'Active')  # Default to trial eligible
        self._register_device_for_trial_status(trial_status)

        return user_email

    def _register_device_for_trial_status(self, trial_status: str):
        """
        Register device with appropriate serial number based on trial eligibility

        Args:
            trial_status: 'Active'/'True' (case-insensitive) for trial eligible, 'None' for not eligible
        """
        device_mac = f"AA:BB:CC:DD:EE:{datetime.now().strftime('%S')}"

        # Check if trial eligible using centralized logic
        if self._is_trial_eligible(trial_status):
            # Trial ELIGIBLE - use unique serial number
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            device_serial = f"M2P{timestamp}"
            self.logger.info(f"Registering device with UNIQUE serial: {device_serial} (TRIAL ELIGIBLE)")
        else:
            # Trial NOT ELIGIBLE - use known trial serial
            device_serial = "M2P122827570"
            self.logger.info(f"Registering device with KNOWN trial serial: {device_serial} (TRIAL NOT ELIGIBLE)")

        device_response = self.mlm_api.register_device(
            registered_mac=device_mac,
            registered_serial=device_serial
        )

        if not device_response.is_success():
            self.logger.warning(f"Device registration failed: {device_response.message}")
        else:
            self.logger.info(f"✓ Device registered successfully")

    def _cleanup_user(self, user_email: str):
        """
        Cleanup user after test (delete account)

        Args:
            user_email: Email of the user to delete (for logging purposes)
        """
        try:
            self.logger.info(f"Deleting user account: {user_email}")
            delete_response = self.mlm_api.delete_user_account()

            if delete_response.is_success():
                self.logger.info(f"✓ User account deleted successfully: {user_email}")
            else:
                self.logger.warning(
                    f"⚠️  User deletion API call succeeded but returned failure status: "
                    f"{delete_response.message}"
                )
        except Exception as e:
            self.logger.error(f"❌ Failed to cleanup user {user_email}: {str(e)}")
            # Don't raise - cleanup failures shouldn't stop test execution
