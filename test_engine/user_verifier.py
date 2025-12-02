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
    
    def verify_from_user_api(
        self, 
        action_name: str, 
        action_result: Dict[str, Any],
        subscription_state: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Verify the result of an action matches expectations
        
        Args:
            action_name: Name of the action executed
            action_result: Result from action execution
            subscription_state: Current subscription state tracking dict (includes subscription_type, 
                              status, dates, is_cancelled, days_advanced)
            
        Returns:
            Verification result dictionary
        """
        # Extract subscription_type from state for backward compatibility
        subscription_type = subscription_state.get('subscription_type') if subscription_state else None
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
        state_days_advanced = subscription_state.get('days_advanced', 0) if subscription_state else 0
        state_prev_expire_date = subscription_state.get('expire_date') if subscription_state else None
        
        # Get subscription config to determine expected status based on trial eligibility
        # For cancel/reactivate/advance_time actions, use the subscription_type from previous purchase
        # For purchase actions, get it from the action config
        if action_type in ['cancel', 'reactivate', 'advance_time'] and subscription_type:
            # Use subscription_type from previous purchase action
            subscription_config = self.subscriptions_config.get(subscription_type, {})
            self.logger.info(f"Using subscription_type from previous action: {subscription_type}")
        else:
            # Get from action config (purchase actions)
            subscription_type = self.actions_config[action_name].get('subscription_type')
            subscription_config = self.subscriptions_config.get(subscription_type, {})
        
        # Special handling for cancel, reactivate, and advance_time actions
        if action_type == 'cancel':
            # After cancel, status should be 4 (cancelled)
            expected_status_code = 4
            expected_status_name = 'cancelled'
            check_trial_period = False
            trial_duration_days = None
            self.logger.info(f"Cancel action detected, expecting status: {expected_status_code} ({expected_status_name})")
        elif action_type == 'advance_time':
            # Calculate expected status after time advancement
            result = self._calculate_status_after_time_advance(
                subscription_state=subscription_state,
                action_result=action_result,
                subscription_config=subscription_config
            )
            expected_status_code = result['expected_status_code']
            expected_status_name = result['expected_status_name']
            check_trial_period = result['check_trial_period']
            trial_duration_days = result['trial_duration_days']
            self.logger.info(f"Advance time detected, expecting status: {expected_status_code} ({expected_status_name})")
        elif action_type == 'reactivate':
            # After reactivate, subscription should return to its original state
            # Use the same logic as purchase: check trial eligibility and subscription support
            supports_trial = subscription_config.get('supports_trial', False)
            
            if supports_trial and self.trial_eligible:
                # User IS trial eligible and plan supports trial - should be in trial
                expected_status_code = 3
                expected_status_name = 'trial'
                check_trial_period = True
                trial_duration_days = subscription_config.get('trial_period_days', 45)
            else:
                # User is NOT trial eligible OR plan doesn't support trial - should be active
                expected_status_code = 1
                expected_status_name = 'active'
                check_trial_period = False
                trial_duration_days = None
            
            self.logger.info(f"Trial eligible: {self.trial_eligible}, Supports trial: {supports_trial}")
            self.logger.info(f"Reactivate action detected, expecting status: {expected_status_code} ({expected_status_name})")
        else:
            # Regular purchase actions - determine based on trial eligibility
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
        
        # Get expected plan code from subscription config (not from verification config)
        expected_plan_code = subscription_config.get('code') if subscription_config else None
        
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
            state_prev_expire_date=state_prev_expire_date
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
        state_prev_expire_date: str = None
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
            
            # Get the correct subscription based on simulated time (for advance_time actions)
            # or the latest subscription (for regular actions)
            latest_sub = self._select_subscription_at_simulated_time(
                subscriptions_response=subscriptions_response,
                state_days_advanced=state_days_advanced
            )
            
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
            elif not check_trial_period and actual_trial_period is not None and actual_status_code != 4:
                # This is supposed to be a non-trial subscription, but has trial_period_days
                # Note: We skip this check for cancelled subscriptions (status=4) as they may retain
                # the trial_period_days field from when they were originally created
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
                    
                    # Check start date validity
                    # Skip "within last hour" check if time has been advanced OR if current action is advance_time
                    if action_type == 'advance_time' or state_days_advanced > 0:
                        # Time advancement scenario - start date should match previous subscription's expire date
                        # (when trial expires, new active subscription starts at trial's end date)
                        if state_prev_expire_date and state_days_advanced > 0:
                            expected_start = datetime.fromisoformat(state_prev_expire_date.replace('Z', '+00:00'))
                            time_diff = abs((start_date - expected_start).total_seconds())
                            if time_diff > 60:  # Allow 1 minute tolerance
                                verification_issues.append(
                                    f"Start date mismatch after time advance: {latest_sub.startDate} "
                                    f"(expected: {state_prev_expire_date}, difference: {time_diff/60:.1f} minutes)"
                                )
                            else:
                                self.logger.info(f"  ✓ Start date matches previous expire date")
                        else:
                            self.logger.info(f"  Skipping start date check (time has been advanced or is being advanced)")
                    else:
                        # For initial purchase: check that start date is recent (within last hour)
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
            
            # Get expected duration from subscription config
            expected_duration_days = subscription_config.get('duration_days') if subscription_config else None
            
            # Calculate expected dates for time advancement scenarios
            expected_start_date = None
            expected_expire_date = None
            
            if action_type == 'advance_time' or state_days_advanced > 0:
                # For time advancement: calculate expected dates
                expected_start_date = state_prev_expire_date if state_prev_expire_date else None
                if expected_start_date and expected_duration_days:
                    try:
                        exp_start = datetime.fromisoformat(expected_start_date.replace('Z', '+00:00'))
                        exp_expire = exp_start + timedelta(days=expected_duration_days)
                        expected_expire_date = exp_expire.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    except Exception as e:
                        self.logger.warning(f"Could not calculate expected dates: {e}")
            
            if verification_issues:
                return {
                    'verified': False,
                    'message': '; '.join(verification_issues),
                    'issues': verification_issues,
                    'expected_status_code': expected_status_code,
                    'expected_plan_code': expected_plan_code,
                    'expected_trial_period_days': trial_duration_days,  # For trial subscriptions
                    'expected_duration_days': expected_duration_days,    # For non-trial subscriptions
                    'expected_start_date': expected_start_date,  # For time advancement scenarios
                    'expected_expire_date': expected_expire_date,  # For time advancement scenarios
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
                    'expected_start_date': expected_start_date,  # For time advancement scenarios
                    'expected_expire_date': expected_expire_date,  # For time advancement scenarios
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
    
    def _calculate_status_after_time_advance(
        self,
        subscription_state: Dict[str, Any],
        action_result: Dict[str, Any],
        subscription_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate expected subscription status after time advancement
        
        IMPORTANT: This framework uses Stripe's TEST CLOCK advancement, NOT real time.
        The backend database does NOT know about simulated time, only Stripe does.
        Therefore, backend status reflects REAL time, not simulated time.
        
        Logic:
        - If in trial (status=3) and NOT cancelled:
            - After trial period → active (status=1) in Stripe
            - Backend creates new subscription after trial
        - If in trial (status=3) and cancelled (status=4):
            - After trial period → status REMAINS cancelled (4)
            - Backend doesn't know time advanced, so it won't change to expired (2)
        - If active (status=1) and NOT cancelled:
            - After subscription period → status REMAINS active (1)
            - Backend doesn't advance time, so won't trigger expiration/renewal
        - If active (status=1) and cancelled (status=4):
            - After current period → status REMAINS cancelled (4)
            - Backend doesn't know time advanced, so it won't change to expired (2)
        
        Args:
            subscription_state: Current subscription state
            action_result: Result from advance_time action
            subscription_config: Subscription configuration
            
        Returns:
            Dict with expected_status_code, expected_status_name, check_trial_period, trial_duration_days
        """
        days_advanced = action_result.get('days_advanced', 0)
        # Note: total_days_advanced will be updated AFTER this verification
        # So we use the PREVIOUS total + current advancement
        previous_days_advanced = subscription_state.get('days_advanced', 0)
        total_days_advanced = previous_days_advanced + days_advanced
        
        # Get current state
        current_status = subscription_state.get('status_code')
        is_cancelled = subscription_state.get('is_cancelled', False)
        trial_period_days = subscription_state.get('trial_period_days')
        
        self.logger.info(f"Calculating expected status after advancing {days_advanced} days")
        self.logger.info(f"Previous days advanced: {previous_days_advanced}, Total: {total_days_advanced}")
        self.logger.info(f"Current state: status={current_status}, cancelled={is_cancelled}, trial_days={trial_period_days}")
        
        # Parse dates to calculate time-based status
        try:
            if subscription_state.get('start_date') and subscription_state.get('expire_date'):
                from datetime import datetime
                # Use the ORIGINAL start date (from first subscription)
                start_date = datetime.fromisoformat(subscription_state['start_date'].replace('Z', '+00:00'))
                expire_date = datetime.fromisoformat(subscription_state['expire_date'].replace('Z', '+00:00'))
                
                # Calculate simulated current time based on total days advanced
                simulated_now = start_date + timedelta(days=total_days_advanced)
                
                self.logger.info(f"Start date: {start_date}")
                self.logger.info(f"Expire date: {expire_date}")
                self.logger.info(f"Simulated now (after {total_days_advanced} days): {simulated_now}")
                
                # Check if we've passed the expire date (in simulated time)
                if simulated_now >= expire_date:
                    # Past expiration (in simulated Stripe time)
                    if is_cancelled:
                        # IMPORTANT: Backend doesn't know about simulated time!
                        # Cancelled subscription stays CANCELLED (not expired)
                        # because backend's real time hasn't reached expire date
                        expected_status_code = 4
                        expected_status_name = 'cancelled'
                        check_trial_period = False
                        trial_duration_days = None
                        self.logger.info(f"→ Cancelled subscription past expire date in Stripe time, but backend status remains CANCELLED (backend uses real time)")
                    else:
                        # Non-cancelled subscription - should auto-renew or expire IN STRIPE
                        # For trial subscriptions that expire, they convert to active (if not cancelled)
                        if trial_period_days and current_status == 3:
                            # Trial expired → Stripe creates NEW active subscription
                            # Backend DOES see this because Stripe webhook notifies it
                            expected_status_code = 1
                            expected_status_name = 'active'
                            check_trial_period = False
                            trial_duration_days = None
                            self.logger.info(f"→ Trial period expired in Stripe, new active subscription created (webhook notifies backend)")
                        else:
                            # Regular subscription - backend doesn't advance time
                            # So status stays as-is (active or whatever it was)
                            expected_status_code = 1
                            expected_status_name = 'active'
                            check_trial_period = False
                            trial_duration_days = None
                            self.logger.info(f"→ Past subscription period in Stripe time, but backend status remains ACTIVE (backend uses real time)")
                else:
                    # Not yet expired - status should remain the same
                    if is_cancelled:
                        expected_status_code = 4
                        expected_status_name = 'cancelled'
                    elif trial_period_days and current_status == 3:
                        expected_status_code = 3
                        expected_status_name = 'trial'
                    else:
                        expected_status_code = 1
                        expected_status_name = 'active'
                    check_trial_period = bool(trial_period_days and current_status == 3)
                    trial_duration_days = trial_period_days if check_trial_period else None
                    self.logger.info(f"→ Still within subscription period, status remains {expected_status_name}")
            else:
                # Can't parse dates, fall back to current status
                self.logger.warning("Could not parse dates for time advancement calculation")
                expected_status_code = current_status or 1
                expected_status_name = 'active'
                check_trial_period = False
                trial_duration_days = None
        
        except Exception as e:
            self.logger.error(f"Error calculating status after time advance: {e}")
            expected_status_code = 1
            expected_status_name = 'active'
            check_trial_period = False
            trial_duration_days = None
        
        return {
            'expected_status_code': expected_status_code,
            'expected_status_name': expected_status_name,
            'check_trial_period': check_trial_period,
            'trial_duration_days': trial_duration_days
        }
    
    def _select_subscription_at_simulated_time(
        self,
        subscriptions_response: Any,
        state_days_advanced: int = 0
    ) -> Any:
        """
        Select the correct subscription based on simulated time
        
        When time is advanced, the API returns multiple subscriptions (past and current).
        We need to select the subscription that is "active" at the simulated current time.
        
        Logic:
        1. If no time advancement (days_advanced=0), return latest subscription
        2. If time advanced, calculate simulated_now and find subscription where:
           start_date <= simulated_now <= expire_date
        
        Args:
            subscriptions_response: Response from get_subscriptions API
            state_days_advanced: Total days advanced via advance_time actions
            
        Returns:
            The subscription that is active at the simulated time
        """
        from datetime import datetime
        
        all_subs = subscriptions_response.subscriptions
        
        # If no time advancement, use default behavior (latest subscription)
        if state_days_advanced == 0 or len(all_subs) == 1:
            return subscriptions_response.get_latest_subscription()
        
        # Time has been advanced - need to find the subscription active at simulated time
        self.logger.info(f"Time advanced by {state_days_advanced} days, selecting subscription at simulated time")
        self.logger.info(f"Found {len(all_subs)} subscription(s) in API response")
        
        try:
            # Get the FIRST (original) subscription's start date as reference
            # Note: API returns subscriptions in order, first is oldest
            original_sub = all_subs[-1]  # Last in list is the oldest
            original_start = datetime.fromisoformat(original_sub.startDate.replace('Z', '+00:00'))
            
            # Calculate simulated current time
            simulated_now = original_start + timedelta(days=state_days_advanced)
            
            self.logger.info(f"Original start date: {original_start}")
            self.logger.info(f"Simulated current time: {simulated_now}")
            
            # Find the subscription that contains simulated_now
            for i, sub in enumerate(all_subs):
                start_date = datetime.fromisoformat(sub.startDate.replace('Z', '+00:00'))
                expire_date = datetime.fromisoformat(sub.expireDate.replace('Z', '+00:00'))
                
                self.logger.info(f"  Sub {i+1} (ID: {sub.id}): {start_date} to {expire_date}")
                
                # Check if simulated_now falls within this subscription period
                if start_date <= simulated_now <= expire_date:
                    self.logger.info(f"  ✓ Selected subscription ID {sub.id} (active at simulated time)")
                    return sub
            
            # If no subscription contains simulated_now, it might be expired
            # Return the latest subscription
            self.logger.warning(f"No subscription contains simulated time, using latest")
            return subscriptions_response.get_latest_subscription()
        
        except Exception as e:
            self.logger.error(f"Error selecting subscription at simulated time: {e}")
            return subscriptions_response.get_latest_subscription()

