"""
User Verifier
Verifies subscription status and expected results after actions from user perspective
"""

import json
import time
from typing import Dict, Any
from pathlib import Path
from datetime import datetime, timedelta
from base.logger import Logger
from api.mlm_api import MlmAPI


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
    
    def verify_from_user_api(self, action_name: str, action_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify the result of an action matches expectations
        
        Args:
            action_name: Name of the action executed
            action_result: Result from action execution
            
        Returns:
            Verification result dictionary
        """
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
        
        # Get subscription config to determine expected status based on trial eligibility
        subscription_type = self.actions_config[action_name].get('subscription_type')
        subscription_config = self.subscriptions_config.get(subscription_type, {})
        
        # Determine expected status based on trial eligibility and subscription config
        supports_trial = subscription_config.get('supports_trial', False)
        
        if supports_trial and self.trial_eligible:
            # User IS trial eligible and plan supports trial
            expected_status_code = subscription_config.get('expected_status_with_trial', 3)
            expected_status_name = subscription_config.get('expected_status_name_with_trial', 'trial')
            check_trial_period = True
            trial_duration_days = subscription_config.get('trial_period_days', 45)
        else:
            # User is NOT trial eligible OR plan doesn't support trial
            expected_status_code = subscription_config.get('expected_status_without_trial', 1)
            expected_status_name = subscription_config.get('expected_status_name_without_trial', 'active')
            check_trial_period = False
            trial_duration_days = None
        
        self.logger.info(f"Trial eligible: {self.trial_eligible}, Supports trial: {supports_trial}")
        self.logger.info(f"Expected status: {expected_status_code} ({expected_status_name})")
        
        # Verify subscription status
        return self._verify_subscription_status(
            expected_status_code=expected_status_code,
            expected_status=expected_status_name,
            expected_plan_code=verification_config.get('expected_plan_code'),
            check_dates=verification_config.get('check_dates', False),
            check_trial_period=check_trial_period,
            trial_duration_days=trial_duration_days,
            subscription_config=subscription_config
        )
    
    def _verify_subscription_status(
        self,
        expected_status_code: int = None,
        expected_status: str = None,
        expected_plan_code: int = None,
        check_dates: bool = False,
        check_trial_period: bool = False,
        trial_duration_days: int = None,
        subscription_config: Dict[str, Any] = None
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
            
        Returns:
            Verification result
        """
        try:
            self.logger.info("Fetching subscription status from API...")
            
            # Get subscriptions - accept first valid response (even if empty)
            # Empty response is valid (e.g., for free users or cancelled subscriptions)
            subscriptions_response = self.mlm_api.get_subscriptions()
            
            # Get status code mapping
            status_codes = self.subscriptions_config.get('status_codes', {})
            
            if not subscriptions_response.has_active_subscription():
                self.logger.info("No active subscription found (may be expected for free/cancelled users)")
                return {
                    'verified': False,
                    'message': 'No active subscription found',
                    'expected_status_code': expected_status_code,
                    'expected_status': expected_status,
                    'actual_status': 'none'
                }
            
            # Get latest subscription
            latest_sub = subscriptions_response.get_latest_subscription()
            
            actual_plan_code = latest_sub.data.package.code
            actual_status_code = latest_sub.status
            actual_status_name = status_codes.get(str(actual_status_code), 'unknown')
            
            # Check if trial_period_days exists (it's a string in the API response)
            actual_trial_period = getattr(latest_sub.data.package, 'trial_period_days', None)
            if actual_trial_period:
                actual_trial_period = int(actual_trial_period)  # Convert string to int
            
            self.logger.info(f"Found subscription:")
            self.logger.info(f"  ID: {latest_sub.id}")
            self.logger.info(f"  Type: {latest_sub.type}")
            self.logger.info(f"  Status Code: {actual_status_code} ({actual_status_name})")
            self.logger.info(f"  Plan Code: {actual_plan_code}")
            self.logger.info(f"  Trial Period Days: {actual_trial_period if actual_trial_period else 'N/A'}")
            self.logger.info(f"  Start Date: {latest_sub.startDate}")
            self.logger.info(f"  Expire Date: {latest_sub.expireDate}")
            
            verification_issues = []
            
            # Verify status code if specified
            if expected_status_code is not None:
                if actual_status_code != expected_status_code:
                    verification_issues.append(
                        f"Status code mismatch: expected {expected_status_code} ({expected_status}), "
                        f"got {actual_status_code} ({actual_status_name})"
                    )
            
            # Verify plan code if specified
            if expected_plan_code is not None:
                if actual_plan_code != expected_plan_code:
                    verification_issues.append(
                        f"Plan code mismatch: expected {expected_plan_code}, got {actual_plan_code}"
                    )
            
            # Verify trial period if this is a trial subscription
            if check_trial_period and trial_duration_days:
                if actual_trial_period is None:
                    verification_issues.append(
                        f"Expected trial subscription with {trial_duration_days} days, "
                        f"but trial_period_days field is missing from API response"
                    )
                elif actual_trial_period != trial_duration_days:
                    verification_issues.append(
                        f"Trial period mismatch: expected {trial_duration_days} days, "
                        f"got {actual_trial_period} days from API"
                    )
                else:
                    self.logger.info(f"✓ Trial period field verified: {actual_trial_period} days")
            elif not check_trial_period and actual_trial_period is not None:
                # This is supposed to be a non-trial subscription, but has trial_period_days
                verification_issues.append(
                    f"Expected non-trial subscription, but trial_period_days={actual_trial_period} "
                    f"found in API response"
                )
            
            # Verify dates if requested
            if check_dates:
                try:
                    start_date = datetime.fromisoformat(latest_sub.startDate.replace('Z', '+00:00'))
                    expire_date = datetime.fromisoformat(latest_sub.expireDate.replace('Z', '+00:00'))
                    now = datetime.now(start_date.tzinfo)
                    
                    self.logger.info(f"Date verification:")
                    self.logger.info(f"  Start date: {start_date}")
                    self.logger.info(f"  Expire date: {expire_date}")
                    self.logger.info(f"  Now: {now}")
                    
                    # Check that start date is recent (within last hour)
                    time_since_start = (now - start_date).total_seconds()
                    if time_since_start < 0 or time_since_start > 3600:
                        verification_issues.append(
                            f"Start date seems incorrect: {latest_sub.startDate} "
                            f"(expected within last hour)"
                        )
                    
                    # Check trial period if applicable
                    if check_trial_period and trial_duration_days:
                        expected_expire = start_date + timedelta(days=trial_duration_days)
                        # Allow 1 day tolerance
                        days_diff = abs((expire_date - expected_expire).days)
                        if days_diff > 1:
                            verification_issues.append(
                                f"Trial period mismatch: expected {trial_duration_days} days, "
                                f"but expire date is {(expire_date - start_date).days} days from start"
                            )
                        else:
                            self.logger.info(f"✓ Trial period duration verified: ~{trial_duration_days} days from dates")
                    else:
                        # Check subscription duration (should be ~365 days for 1-year)
                        duration_days = (expire_date - start_date).days
                        self.logger.info(f"Subscription duration: {duration_days} days")
                        
                        # For 1-year subscriptions, expect ~365 days (allow 1 day tolerance)
                        if abs(duration_days - 365) > 1:
                            verification_issues.append(
                                f"Subscription duration seems incorrect: {duration_days} days "
                                f"(expected ~365 for 1-year subscription)"
                            )
                        
                except Exception as date_error:
                    verification_issues.append(f"Date parsing error: {str(date_error)}")
            
            # Return result
            # Get expected duration from subscription config
            expected_duration_days = subscription_config.get('duration_days') if subscription_config else None
            
            if verification_issues:
                return {
                    'verified': False,
                    'message': '; '.join(verification_issues),
                    'issues': verification_issues,
                    'expected_status_code': expected_status_code,
                    'expected_plan_code': expected_plan_code,
                    'expected_trial_period_days': trial_duration_days,  # For trial subscriptions
                    'expected_duration_days': expected_duration_days,    # For non-trial subscriptions
                    'subscription': {
                        'id': latest_sub.id,
                        'type': latest_sub.type,
                        'status_code': actual_status_code,
                        'status_name': actual_status_name,
                        'plan_code': actual_plan_code,
                        'trial_period_days': actual_trial_period,
                        'start_date': latest_sub.startDate,
                        'expire_date': latest_sub.expireDate
                    }
                }
            else:
                return {
                    'verified': True,
                    'message': 'Subscription verified successfully',
                    'expected_status_code': expected_status_code,
                    'expected_plan_code': expected_plan_code,
                    'expected_trial_period_days': trial_duration_days,  # For trial subscriptions
                    'expected_duration_days': expected_duration_days,    # For non-trial subscriptions
                    'subscription': {
                        'id': latest_sub.id,
                        'type': latest_sub.type,
                        'status_code': actual_status_code,
                        'status_name': actual_status_name,
                        'plan_code': actual_plan_code,
                        'trial_period_days': actual_trial_period,
                        'start_date': latest_sub.startDate,
                        'expire_date': latest_sub.expireDate
                    }
                }
        
        except Exception as e:
            self.logger.error(f"Error verifying subscription: {str(e)}")
            return {
                'verified': False,
                'message': f'Verification error: {str(e)}',
                'error': str(e)
            }

