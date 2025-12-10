"""
User Verifier
Verifies subscription status and expected results after actions from user perspective
"""

import json
import time
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
from base.logger import Logger
from api.mlm_api import MlmAPI
from test_engine.subscription_expectations import SubscriptionExpectations
from test_engine.subscription_state_manager import SubscriptionStateManager
from models.types import VerificationType, SubscriptionState, ExpectedPaymentResult



class UserVerifier:
    """
    Verify subscription status and results against expected configuration from user API
    """
    
    def __init__(self, mlm_api: MlmAPI, trial_eligible: bool = True):
        """
        Initialize verifier
        
        Args:
            mlm_api: MLM API client instance
            trial_eligible: Whether the user is trial eligible (based on device serial)
        """
        self.mlm_api = mlm_api
        self.trial_eligible = trial_eligible
        self.logger = Logger(__name__)
        
        # Load action configurations
        config_path = Path(__file__).parent.parent / 'config' / 'actions.json'
        with open(config_path, 'r') as f:
            self.actions_config = json.load(f)
        
        # Load subscription configurations
        subscriptions_path = Path(__file__).parent.parent / 'config' / 'subscriptions.json'
        with open(subscriptions_path, 'r') as f:
            self.subscriptions_config = json.load(f)

        self.expectations = SubscriptionExpectations(trial_eligible=trial_eligible)
        self.state_manager = SubscriptionStateManager(mlm_api)


    
    def verify_from_user_api(
        self, 
        action_name: str, 
        action_result: Dict[str, Any],
        subscription_state: Optional[SubscriptionState] = None,
        subscription_state_snapshot: Optional[SubscriptionState] = None
    ) -> Dict[str, Any]:
        """
        Verify the result of an action matches expectations
        
        Args:
            action_name: Name of the action executed
            action_result: Result from action execution
            subscription_state: Current subscription state
            subscription_state_snapshot: State snapshot before action (for declined card verification)
            
        Returns:
            Verification result dictionary
        """
        # Check if this is a declined card - verify state unchanged
        expected_result = action_result.get('expected_result')
        if expected_result == ExpectedPaymentResult.DECLINED.value and subscription_state_snapshot:
            self.logger.info("Verifying declined card - subscription state should be unchanged")
            # Get current state from API
            current_state = self.state_manager.get_current_state()
            # Compare with snapshot
            comparison_result = self.state_manager.verify_states_are_same(
                subscription_state_snapshot,
                current_state
            )
            return {
                'verified': comparison_result['verified'],
                'message': comparison_result['message'],
                'checks': comparison_result['checks'],
                'differences': comparison_result.get('differences', []),
                'verification_type': VerificationType.USER_API.value,
                'action_name': action_name
            }
        
        # Extract subscription_type from state
        subscription_type = subscription_state.subscription_type if subscription_state else None
        self.logger.info(f"Verifying action result: {action_name}")
        
        # Check if action exists
        if action_name not in self.actions_config:
            return {
                'verified': False,
                'message': f'Unknown action: {action_name}'
            }
        
        action_config = self.actions_config[action_name]
        verification_config = action_config.get('verification', {})
        
        # If action failed, don't verify subscription status
        if not action_result.get('success'):
            self.logger.info("Action failed, skipping verification")
            return {
                'verified': False,
                'message': 'Action failed, no verification performed',
                'action_result': action_result
            }
        
        # Check if subscription status verification is required
        if not verification_config.get('check_subscription_status'):
            self.logger.info("No subscription verification required for this action")
            return {
                'verified': True,
                'message': 'No verification required'
            }
        
        # Get action type to handle special cases (cancel, reactivate)
        action_type = action_config.get('action_type')
        
        # Extract commonly used state values with defaults for safer access throughout the function
        state_days_advanced = subscription_state.days_advanced if subscription_state else 0
        state_prev_expire_date = subscription_state.expire_date if subscription_state else None
        
        # Get subscription config to determine expected status based on trial eligibility
        # For cancel/refund/reactivate/advance_time actions, use the subscription_type from previous purchase
        # For purchase actions, get it from the action config
        if action_type in ['cancel', 'refund', 'reactivate', 'advance_time'] and subscription_type:
            # Use subscription_type from previous purchase action
            subscription_config = self.subscriptions_config.get(subscription_type, {})
            self.logger.info(f"Using subscription_type from previous action: {subscription_type}")
        else:
            # Get from action config (purchase actions)
            subscription_type = self.actions_config[action_name].get('subscription_type')
            subscription_config = self.subscriptions_config.get(subscription_type, {})
        
        # Calculate expected status and other information for cancel, refund, reactivate, and advance_time actions
        status_result = self.expectations.calculate_expected_status(
            action_type=action_type,
            subscription_type=subscription_type,
            subscription_state=subscription_state,
            subscription_config=subscription_config
        )
        # Get expected plan code from subscription config (not from verification config)
        expected_plan_code = subscription_config.get('code') if subscription_config else None
        expected_status_code = status_result['expected_status_code']
        expected_status_name = status_result['expected_status_name']
        check_trial_period = status_result['check_trial_period']
        trial_duration_days = status_result['trial_duration_days']




        # Verify subscription status
        return self._verify_subscription_status(
            expected_status_code=expected_status_code,
            expected_status=expected_status_name,
            expected_plan_code=expected_plan_code,
            check_dates=verification_config.get('check_dates', False),
            check_trial_period=check_trial_period,
            trial_duration_days=trial_duration_days,
            subscription_config=subscription_config,
            action_type=action_type,
            state_days_advanced=state_days_advanced,
            state_prev_expire_date=state_prev_expire_date,
            subscription_state=subscription_state
        )
    
    def _verify_subscription_status(
        self,
        expected_status_code: int = None,
        expected_status: str = None,
        expected_plan_code: int = None,
        check_dates: bool = False,
        check_trial_period: bool = False,
        trial_duration_days: int = None,
        subscription_config: Dict[str, Any] = None,
        action_type: str = None,
        state_days_advanced: int = 0,
        state_prev_expire_date: str = None,
        subscription_state: Optional[SubscriptionState] = None
    ) -> Dict[str, Any]:
        """
        Verify subscription status via MLM API
        
        Args:
            expected_status_code: Expected subscription status code (1=active, 3=trial, etc.)
            expected_status: Expected subscription status name (e.g., 'active', 'trial')
            expected_plan_code: Expected plan code
            check_dates: Whether to verify start and expire dates
            check_trial_period: Whether to verify trial period dates
            trial_duration_days: Expected trial duration in days
            subscription_config: Subscription configuration dictionary
            action_type: Type of action being verified (purchase, cancel, advance_time, etc.)
            state_days_advanced: Total days advanced via advance_time actions
            state_prev_expire_date: Previous subscription's expire date (for time advancement verification)
            
        Returns:
            Verification result
        """
        try:
            self.logger.info("Fetching subscription status from API...")
            
            # Get current subscription state (with time-aware selection if days_advanced > 0)
            current_state = self.state_manager.get_current_state(days_advanced=state_days_advanced)
            
            if not current_state.exists:
                self.logger.info("No active subscription found (may be expected for free/cancelled/refunded users)")
                
                # For refund actions, no active subscription is expected (refunds only show in Admin API)
                if action_type == 'refund':
                    self.logger.info("✓ Refund action: No active subscription is expected behavior")
                    return {
                        'verified': True,
                        'message': 'No active subscription (expected for refunded users)',
                        'expected_status_code': expected_status_code,
                        'expected_status': expected_status,
                        'actual_status': 'none (refunded subscription only visible in Admin API)'
                    }
                
                return {
                    'verified': False,
                    'message': 'No active subscription found',
                    'expected_status_code': expected_status_code,
                    'expected_status': expected_status,
                    'actual_status': 'none'
                }
            
            # Extract values from current state
            actual_plan_code = current_state.plan_code
            actual_status_code = current_state.status_code
            actual_status_name = current_state.status_name
            actual_trial_period = current_state.trial_period_days
            
            self.logger.info(f"Found subscription:")
            self.logger.info(f"  ID: {current_state.subscription_id}")
            self.logger.info(f"  Type Code: {current_state.subscription_type_code}")
            self.logger.info(f"  Status Code: {actual_status_code} ({actual_status_name})")
            self.logger.info(f"  Plan Code: {actual_plan_code}")
            self.logger.info(f"  Trial Period Days: {actual_trial_period if actual_trial_period else 'N/A'}")
            self.logger.info(f"  Start Date: {current_state.start_date}")
            self.logger.info(f"  Expire Date: {current_state.expire_date}")
            
            verification_issues = []
            checks = {}  # Granular verification results
            
            # Verify status code if specified
            if expected_status_code is not None:
                status_passed = actual_status_code == expected_status_code
                checks['status_code'] = {
                    'passed': status_passed,
                    'expected': expected_status_code,
                    'actual': actual_status_code,
                    'message': actual_status_name
                }
                if not status_passed:
                    verification_issues.append(
                        f"Status code mismatch: expected {expected_status_code} ({expected_status}), "
                        f"got {actual_status_code} ({actual_status_name})"
                    )
            
            # Verify plan code if specified
            if expected_plan_code is not None:
                plan_passed = actual_plan_code == expected_plan_code
                checks['plan_code'] = {
                    'passed': plan_passed,
                    'expected': expected_plan_code,
                    'actual': actual_plan_code,
                    'message': f"Plan {actual_plan_code}"
                }
                if not plan_passed:
                    verification_issues.append(
                        f"Plan code mismatch: expected {expected_plan_code}, got {actual_plan_code}"
                    )
            
            # Verify subscription type (always web = 2)
            expected_type = 2
            actual_type = current_state.subscription_type_code
            type_passed = actual_type == expected_type
            checks['subscription_type'] = {
                'passed': type_passed,
                'expected': expected_type,
                'actual': actual_type,
                'message': 'web' if actual_type == 2 else f'type {actual_type}'
            }
            if not type_passed:
                verification_issues.append(
                    f"Subscription type mismatch: expected {expected_type}, got {actual_type}"
                )
            
            # Verify trial period if this is a trial subscription
            if check_trial_period and trial_duration_days:
                trial_passed = False
                trial_message = ""
                if actual_trial_period is None:
                    trial_message = f"Expected {trial_duration_days} days but field missing"
                    verification_issues.append(
                        f"Expected trial subscription with {trial_duration_days} days, "
                        f"but trial_period_days field is missing from API response"
                    )
                elif actual_trial_period != trial_duration_days:
                    trial_message = f"Expected {trial_duration_days} days, got {actual_trial_period}"
                    verification_issues.append(
                        f"Trial period mismatch: expected {trial_duration_days} days, "
                        f"got {actual_trial_period} days from API"
                    )
                else:
                    trial_passed = True
                    trial_message = f"{actual_trial_period} days"
                    self.logger.info(f"✓ Trial period field verified: {actual_trial_period} days")
                
                checks['trial_period'] = {
                    'passed': trial_passed,
                    'expected': trial_duration_days,
                    'actual': actual_trial_period,
                    'message': trial_message
                }
            elif not check_trial_period and actual_trial_period is not None and actual_status_code != 4:
                # This is supposed to be a non-trial subscription, but has trial_period_days
                # Note: We skip this check for cancelled subscriptions (status=4) as they may retain
                # the trial_period_days field from when they were originally created
                checks['trial_period'] = {
                    'passed': False,
                    'expected': None,
                    'actual': actual_trial_period,
                    'message': f"Unexpected trial_period_days={actual_trial_period}"
                }
                verification_issues.append(
                    f"Expected non-trial subscription, but trial_period_days={actual_trial_period} "
                    f"found in API response"
                )
            
            # Verify dates if requested
            if check_dates:
                try:
                    start_date = datetime.fromisoformat(current_state.start_date.replace('Z', '+00:00'))
                    expire_date = datetime.fromisoformat(current_state.expire_date.replace('Z', '+00:00'))
                    now = datetime.now(start_date.tzinfo)
                    
                    self.logger.info(f"Date verification:")
                    self.logger.info(f"  Start date: {start_date}")
                    self.logger.info(f"  Expire date: {expire_date}")
                    self.logger.info(f"  Now: {now}")
                    
                    # Check start date validity
                    # Skip "within last hour" check if time has been advanced OR if current action is advance_time
                    if action_type == 'advance_time' or state_days_advanced > 0:
                        # Date verification happens after _calculate_expected_dates() is called
                        # This ensures cancellation state is properly considered
                        self.logger.info(f"  Date verification deferred to after expected dates calculation")
                    else:
                        # For initial purchase: check that start date is recent (within last hour)
                        time_since_start = (now - start_date).total_seconds()
                        start_passed = time_since_start >= 0 and time_since_start <= 3600
                        checks['start_date'] = {
                            'passed': start_passed,
                            'expected': 'within last hour',
                            'actual': current_state.start_date,
                            'message': f'{int(time_since_start/60)} minutes ago' if time_since_start > 0 else 'in future'
                        }
                        if not start_passed:
                            verification_issues.append(
                                f"Start date seems incorrect: {current_state.start_date} "
                                f"(expected within last hour)"
                            )
                    
                    # Check trial period if applicable
                    if check_trial_period and trial_duration_days:
                        expected_expire = start_date + timedelta(days=trial_duration_days)
                        # Allow 1 day tolerance
                        days_diff = abs((expire_date - expected_expire).days)
                        trial_dates_passed = days_diff <= 1
                        actual_days = (expire_date - start_date).days
                        checks['trial_period_dates'] = {
                            'passed': trial_dates_passed,
                            'expected': f'{trial_duration_days} days',
                            'actual': f'{actual_days} days',
                            'message': f'~{actual_days} days from dates'
                        }
                        if not trial_dates_passed:
                            verification_issues.append(
                                f"Trial period mismatch: expected {trial_duration_days} days, "
                                f"but expire date is {actual_days} days from start"
                            )
                        else:
                            self.logger.info(f"✓ Trial period duration verified: ~{trial_duration_days} days from dates")
                        
                except Exception as date_error:
                    verification_issues.append(f"Date parsing error: {str(date_error)}")
            
            # Get expected duration from subscription config
            expected_duration_months = subscription_config.get('duration_months') if subscription_config else None
            
            # Calculate expected dates based on action type and cancellation state
            # This properly handles:
            # - purchase/cancel/refund/reactivate: expect actual dates
            # - advance_time + cancelled: expect unchanged dates (won't renew)
            # - advance_time + not cancelled: calculate new dates if past expiration
            expected_start_date, expected_expire_date = self.expectations.calculate_expected_dates(
                action_type=action_type,
                subscription_state=subscription_state,
                actual_start_date=current_state.start_date,
                actual_expire_date=current_state.expire_date,
                subscription_config=subscription_config
            )
            
            self.logger.info(f"Expected dates calculated:")
            self.logger.info(f"  Expected Start: {expected_start_date}")
            self.logger.info(f"  Expected Expire: {expected_expire_date}")

            # Verify the calculated expected dates against actual dates
            if expected_start_date and expected_expire_date and (action_type == 'advance_time' or state_days_advanced > 0):
                try:
                    actual_start = datetime.fromisoformat(current_state.start_date.replace('Z', '+00:00'))
                    actual_expire = datetime.fromisoformat(current_state.expire_date.replace('Z', '+00:00'))
                    expected_start = datetime.fromisoformat(expected_start_date.replace('Z', '+00:00'))
                    expected_expire = datetime.fromisoformat(expected_expire_date.replace('Z', '+00:00'))

                    # Compare start dates (allow 1 minute tolerance)
                    start_diff_seconds = abs((actual_start - expected_start).total_seconds())
                    start_passed = start_diff_seconds <= 60
                    checks['start_date'] = {
                        'passed': start_passed,
                        'expected': expected_start_date,
                        'actual': current_state.start_date,
                        'message': f'matches expected' if start_passed else f'difference: {start_diff_seconds/60:.1f} minutes'
                    }
                    if not start_passed:
                        verification_issues.append(
                            f"Start date mismatch: {current_state.start_date} "
                            f"(expected: {expected_start_date}, difference: {start_diff_seconds/60:.1f} minutes)"
                        )
                    else:
                        self.logger.info(f"  ✓ Start date verified: matches expected")

                    # Compare expire dates (allow 1 minute tolerance)
                    expire_diff_seconds = abs((actual_expire - expected_expire).total_seconds())
                    expire_passed = expire_diff_seconds <= 60
                    checks['expire_date'] = {
                        'passed': expire_passed,
                        'expected': expected_expire_date,
                        'actual': current_state.expire_date,
                        'message': f'matches expected' if expire_passed else f'difference: {expire_diff_seconds/60:.1f} minutes'
                    }
                    if not expire_passed:
                        verification_issues.append(
                            f"Expire date mismatch: {current_state.expire_date} "
                            f"(expected: {expected_expire_date}, difference: {expire_diff_seconds/60:.1f} minutes)"
                        )
                    else:
                        self.logger.info(f"  ✓ Expire date verified: matches expected")

                except Exception as e:
                    self.logger.warning(f"Could not verify expected dates: {e}")


            if verification_issues:
                return {
                    'verified': False,
                    'message': '; '.join(verification_issues),
                    'issues': verification_issues,
                    'checks': checks,  # Granular verification results
                    'expected_status_code': expected_status_code,
                    'expected_plan_code': expected_plan_code,
                    'expected_trial_period_days': trial_duration_days,  # For trial subscriptions
                    'expected_duration_months': expected_duration_months,    # For non-trial subscriptions
                    'expected_start_date': expected_start_date,  # For time advancement scenarios
                    'expected_expire_date': expected_expire_date,  # For time advancement scenarios
                    'subscription': {
                        'id': current_state.subscription_id,
                        'type': current_state.subscription_type_code,
                        'status_code': actual_status_code,
                        'status_name': actual_status_name,
                        'plan_code': actual_plan_code,
                        'trial_period_days': actual_trial_period,
                        'start_date': current_state.start_date,
                        'expire_date': current_state.expire_date
                    }
                }
            else:
                return {
                    'verified': True,
                    'message': 'Subscription verified successfully',
                    'checks': checks,  # Granular verification results
                    'expected_status_code': expected_status_code,
                    'expected_plan_code': expected_plan_code,
                    'expected_trial_period_days': trial_duration_days,  # For trial subscriptions
                    'expected_duration_months': expected_duration_months,    # For non-trial subscriptions
                    'expected_start_date': expected_start_date,  # For time advancement scenarios
                    'expected_expire_date': expected_expire_date,  # For time advancement scenarios
                    'subscription': {
                        'id': current_state.subscription_id,
                        'type': current_state.subscription_type_code,
                        'status_code': actual_status_code,
                        'status_name': actual_status_name,
                        'plan_code': actual_plan_code,
                        'trial_period_days': actual_trial_period,
                        'start_date': current_state.start_date,
                        'expire_date': current_state.expire_date
                    }
                }
        
        except Exception as e:
            self.logger.error(f"Error verifying subscription: {str(e)}")
            return {
                'verified': False,
                'message': f'Verification error: {str(e)}',
                'error': str(e)
            }