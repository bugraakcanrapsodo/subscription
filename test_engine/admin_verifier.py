"""
Admin Verifier
Verifies subscriptions using admin endpoint data and cross-references with user endpoint
"""

import json
import time
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta
from base.logger import Logger
from api.mlm_api import MlmAPI
from models.subscription import GetAdminSubscriptionsResponse, AdminSubscription


class AdminVerifier:
    """
    Verify subscriptions from admin panel and cross-check with user data
    """
    
    def __init__(self, mlm_api: MlmAPI):
        """
        Initialize admin verifier
        
        Args:
            mlm_api: MLM API client instance
        """
        self.mlm_api = mlm_api
        self.logger = Logger(__name__)
        
        # Load subscription configurations
        subscriptions_path = Path(__file__).parent.parent / 'config' / 'subscriptions.json'
        with open(subscriptions_path, 'r') as f:
            self.subscriptions_config = json.load(f)
    
    def verify_from_admin_api(
        self,
        user_email: str,
        expected_status_code: int = None,
        expected_plan_code: int = None,
        expected_duration_days: int = None,
        expected_trial_period_days: int = None,
        expected_start_date: str = None,
        expected_expire_date: str = None,
        check_dates: bool = False,
        subscription_state: Dict[str, Any] = None,
        action_type: str = None
    ) -> Dict[str, Any]:
        """
        Verify subscription via Admin API
        
        Args:
            user_email: User email to search for
            expected_status_code: Expected status code
            expected_plan_code: Expected plan code (not available in admin data)
            expected_duration_days: Expected subscription duration in days
            expected_trial_period_days: Expected trial period in days
            check_dates: Whether to verify dates
            
        Returns:
            Verification result dictionary
        """
        try:
            self.logger.info(f"Verifying subscription in admin panel for: {user_email}")
            
            # Get admin subscriptions - accept first valid response (even if empty)
            # Empty response is valid (e.g., for free users or cancelled subscriptions)
            # Note: Executor already waits 2s for webhook processing before calling verifiers
            admin_subs = self.mlm_api.get_admin_subscriptions()
            
            # Find user's subscriptions (may be multiple after time advancement)
            all_admin_subs = admin_subs.get_all_subscriptions_by_email(user_email)
            
            if not all_admin_subs:
                self.logger.info(f"No subscription found in admin panel for {user_email} (may be expected for free/cancelled users)")
                return {
                    'verified': False,
                    'message': f'Subscription not found in admin panel for {user_email}',
                    'admin_subscription': None
                }
            
            # Select the correct subscription based on simulated time
            state_days_advanced = subscription_state.get('days_advanced', 0) if subscription_state else 0
            admin_sub = self._select_admin_subscription_at_simulated_time(
                all_subscriptions=all_admin_subs,
                state_days_advanced=state_days_advanced
            )
            
            # Get status and type names
            status_codes = self.subscriptions_config.get('status_codes', {})
            type_codes = self.subscriptions_config.get('type_codes', {})
            
            actual_status_code = admin_sub.status
            actual_status_name = status_codes.get(str(actual_status_code), 'unknown')
            actual_type_code = admin_sub.type
            actual_type_name = type_codes.get(str(actual_type_code), 'unknown')
            
            self.logger.info(f"Found subscription in admin panel:")
            self.logger.info(f"  Subscription ID: {admin_sub.id}")
            self.logger.info(f"  User ID: {admin_sub.userId}")
            self.logger.info(f"  Email: {admin_sub.email}")
            self.logger.info(f"  Type: {actual_type_code} ({actual_type_name})")
            self.logger.info(f"  Status: {actual_status_code} ({actual_status_name})")
            self.logger.info(f"  MLM Version: {admin_sub.mlmVersion}")
            self.logger.info(f"  Start Date: {admin_sub.startDate}")
            self.logger.info(f"  Expire Date: {admin_sub.expireDate}")
            
            verification_issues = []
            
            # Verify status code if specified
            if expected_status_code is not None:
                if actual_status_code != expected_status_code:
                    verification_issues.append(
                        f"Status code mismatch: expected {expected_status_code}, "
                        f"got {actual_status_code} ({actual_status_name})"
                    )
            
            # Note: Admin endpoint doesn't have plan code, only user endpoint has it
            if expected_plan_code is not None:
                self.logger.warning(
                    "Plan code verification not available in admin endpoint. "
                    "Use user endpoint verification for plan code."
                )
            
            # Calculate trial period from dates if status is trial (3) or cancelled (4)
            # For cancelled subscriptions, we need to know if they were cancelled during trial
            trial_period_days = None
            if actual_status_code in [3, 4] and admin_sub.startDate and admin_sub.expireDate:
                try:
                    start_date = datetime.fromisoformat(admin_sub.startDate.replace('Z', '+00:00'))
                    expire_date = datetime.fromisoformat(admin_sub.expireDate.replace('Z', '+00:00'))
                    duration_days = (expire_date - start_date).days
                    
                    # If duration matches expected trial period, set trial_period_days
                    # Trial periods are typically 30, 45, or 60 days
                    if expected_trial_period_days and abs(duration_days - expected_trial_period_days) <= 1:
                        trial_period_days = duration_days
                        self.logger.info(f"  Trial Period: {trial_period_days} days (calculated from dates)")
                    elif duration_days < 90:  # Assume anything < 90 days is likely a trial
                        trial_period_days = duration_days
                        self.logger.info(f"  Possible Trial Period: {trial_period_days} days (calculated from dates)")
                except Exception as e:
                    self.logger.warning(f"Could not calculate trial period: {e}")
            
            # Verify dates if requested
            if check_dates:
                try:
                    start_date = datetime.fromisoformat(admin_sub.startDate.replace('Z', '+00:00'))
                    expire_date = datetime.fromisoformat(admin_sub.expireDate.replace('Z', '+00:00'))
                    now = datetime.now(start_date.tzinfo)
                    
                    self.logger.info(f"Date verification:")
                    self.logger.info(f"  Start date: {start_date}")
                    self.logger.info(f"  Expire date: {expire_date}")
                    self.logger.info(f"  Now: {now}")
                    
                    # Check start date validity
                    state_days_advanced = subscription_state.get('days_advanced', 0) if subscription_state else 0
                    state_prev_expire_date = subscription_state.get('expire_date') if subscription_state else None
                    
                    # Skip "within last hour" check if time has been advanced OR if current action is advance_time
                    if action_type == 'advance_time' or state_days_advanced > 0:
                        # Time advancement scenario - start date should match previous subscription's expire date
                        if state_prev_expire_date and state_days_advanced > 0:
                            expected_start = datetime.fromisoformat(state_prev_expire_date.replace('Z', '+00:00'))
                            time_diff = abs((start_date - expected_start).total_seconds())
                            if time_diff > 60:  # Allow 1 minute tolerance
                                verification_issues.append(
                                    f"Start date mismatch after time advance: {admin_sub.startDate} "
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
                                f"Start date seems incorrect: {admin_sub.startDate} "
                                f"(expected within last hour)"
                            )
                    
                    # Calculate duration
                    duration_days = (expire_date - start_date).days
                    self.logger.info(f"  Subscription duration: {duration_days} days")
                    
                except Exception as date_error:
                    verification_issues.append(f"Date parsing error: {str(date_error)}")
            
            # Note: expected_start_date and expected_expire_date are passed from User API verification
            # to ensure consistency between User API and Admin API verifications
            # They are already calculated in user_verifier.py based on subscription state
            
            # Return result
            if verification_issues:
                return {
                    'verified': False,
                    'message': '; '.join(verification_issues),
                    'issues': verification_issues,
                    'expected_status_code': expected_status_code,
                    'expected_subscription_type': 2,  # Web type
                    'expected_duration_days': expected_duration_days,
                    'expected_trial_period_days': expected_trial_period_days,
                    'expected_start_date': expected_start_date,  # For time advancement scenarios
                    'expected_expire_date': expected_expire_date,  # For time advancement scenarios
                    'admin_subscription': {
                        'id': admin_sub.id,
                        'userId': admin_sub.userId,
                        'email': admin_sub.email,
                        'type': actual_type_code,
                        'type_name': actual_type_name,
                        'status': actual_status_code,
                        'status_name': actual_status_name,
                        'mlmVersion': admin_sub.mlmVersion,
                        'startDate': admin_sub.startDate,
                        'expireDate': admin_sub.expireDate,
                        'trial_period_days': trial_period_days
                    }
                }
            else:
                return {
                    'verified': True,
                    'message': 'Subscription verified in admin panel',
                    'expected_status_code': expected_status_code,
                    'expected_subscription_type': 2,  # Web type
                    'expected_duration_days': expected_duration_days,
                    'expected_trial_period_days': expected_trial_period_days,
                    'expected_start_date': expected_start_date,  # For time advancement scenarios
                    'expected_expire_date': expected_expire_date,  # For time advancement scenarios
                    'admin_subscription': {
                        'id': admin_sub.id,
                        'userId': admin_sub.userId,
                        'email': admin_sub.email,
                        'type': actual_type_code,
                        'type_name': actual_type_name,
                        'status': actual_status_code,
                        'status_name': actual_status_name,
                        'mlmVersion': admin_sub.mlmVersion,
                        'startDate': admin_sub.startDate,
                        'expireDate': admin_sub.expireDate,
                        'trial_period_days': trial_period_days
                    }
                }
        
        except Exception as e:
            self.logger.error(f"Error verifying subscription in admin panel: {str(e)}")
            return {
                'verified': False,
                'message': f'Admin verification error: {str(e)}',
                'error': str(e),
                'admin_subscription': None
            }
    
    def cross_verify_user_and_admin(
        self,
        user_email: str,
        user_verification: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Cross-verify subscription data from both user and admin endpoints
        
        Args:
            user_email: User email
            user_verification: Verification result from user endpoint
            
        Returns:
            Cross-verification result
        """
        self.logger.info("Cross-verifying user and admin data...")
        
        # Verify in admin
        admin_verification = self.verify_from_admin_api(
            user_email=user_email,
            check_dates=False  # Already checked in user verification
        )
        
        # Check if both verified
        user_verified = user_verification.get('verified', False)
        admin_verified = admin_verification.get('verified', False)
        
        if not user_verified:
            return {
                'cross_verified': False,
                'message': 'User endpoint verification failed',
                'user_verification': user_verification,
                'admin_verification': admin_verification
            }
        
        if not admin_verified:
            return {
                'cross_verified': False,
                'message': 'Admin endpoint verification failed',
                'user_verification': user_verification,
                'admin_verification': admin_verification
            }
        
        # Both verified - check consistency
        user_sub = user_verification.get('subscription', {})
        admin_sub = admin_verification.get('admin_subscription', {})
        
        consistency_issues = []
        
        # Check subscription ID matches
        if user_sub.get('id') != admin_sub.get('id'):
            consistency_issues.append(
                f"Subscription ID mismatch: user={user_sub.get('id')}, admin={admin_sub.get('id')}"
            )
        
        # Check status matches
        if user_sub.get('status_code') != admin_sub.get('status'):
            consistency_issues.append(
                f"Status mismatch: user={user_sub.get('status_code')}, admin={admin_sub.get('status')}"
            )
        
        # Check dates match
        if user_sub.get('start_date') != admin_sub.get('startDate'):
            consistency_issues.append(
                f"Start date mismatch: user={user_sub.get('start_date')}, admin={admin_sub.get('startDate')}"
            )
        
        if user_sub.get('expire_date') != admin_sub.get('expireDate'):
            consistency_issues.append(
                f"Expire date mismatch: user={user_sub.get('expire_date')}, admin={admin_sub.get('expireDate')}"
            )
        
        if consistency_issues:
            return {
                'cross_verified': False,
                'message': 'Inconsistency between user and admin data: ' + '; '.join(consistency_issues),
                'issues': consistency_issues,
                'user_verification': user_verification,
                'admin_verification': admin_verification
            }
        else:
            self.logger.info("✓ Cross-verification successful: User and admin data match")
            return {
                'cross_verified': True,
                'message': 'User and admin data verified and consistent',
                'subscription_id': user_sub.get('id'),
                'status': user_sub.get('status_code'),
                'user_verification': user_verification,
                'admin_verification': admin_verification
            }
    
    def get_subscription_details_by_code(self, plan_code: int) -> Optional[Dict[str, Any]]:
        """
        Get subscription details by plan code
        
        Args:
            plan_code: Plan code from API
            
        Returns:
            Subscription details or None if not found
        """
        for sub_type, sub_config in self.subscriptions_config.items():
            if sub_type in ['status_codes', 'type_codes']:
                continue
            if sub_config.get('code') == plan_code:
                return sub_config
        return None
    
    def _select_admin_subscription_at_simulated_time(
        self,
        all_subscriptions: list,
        state_days_advanced: int = 0
    ):
        """
        Select the correct admin subscription based on simulated time
        
        When time is advanced, multiple subscriptions may exist for the same user.
        We need to select the one that is "active" at the simulated current time.
        
        Args:
            all_subscriptions: List of AdminSubscription objects for a user
            state_days_advanced: Total days advanced via advance_time actions
            
        Returns:
            The subscription that is active at the simulated time
        """
        # If no time advancement or only one subscription, return first/only one
        if state_days_advanced == 0 or len(all_subscriptions) == 1:
            return all_subscriptions[0]
        
        # Time has been advanced - need to find the subscription active at simulated time
        self.logger.info(f"Time advanced by {state_days_advanced} days, selecting admin subscription at simulated time")
        self.logger.info(f"Found {len(all_subscriptions)} subscription(s) for user in admin panel")
        
        try:
            # Sort subscriptions by start date (oldest first)
            sorted_subs = sorted(all_subscriptions, key=lambda s: s.startDate)
            
            # Get the FIRST (original) subscription's start date as reference
            original_start = datetime.fromisoformat(sorted_subs[0].startDate.replace('Z', '+00:00'))
            
            # Calculate simulated current time
            simulated_now = original_start + timedelta(days=state_days_advanced)
            
            self.logger.info(f"Original start date: {original_start}")
            self.logger.info(f"Simulated current time: {simulated_now}")
            
            # Find the subscription that contains simulated_now
            for i, sub in enumerate(sorted_subs):
                start_date = datetime.fromisoformat(sub.startDate.replace('Z', '+00:00'))
                expire_date = datetime.fromisoformat(sub.expireDate.replace('Z', '+00:00'))
                
                self.logger.info(f"  Admin Sub {i+1} (ID: {sub.subscriptionId}): {start_date} to {expire_date}")
                
                # Check if simulated_now falls within this subscription period
                if start_date <= simulated_now <= expire_date:
                    self.logger.info(f"  ✓ Selected admin subscription ID {sub.subscriptionId} (active at simulated time)")
                    return sub
            
            # If no subscription contains simulated_now, return the latest
            self.logger.warning(f"No admin subscription contains simulated time, using latest")
            return sorted_subs[-1]
        
        except Exception as e:
            self.logger.error(f"Error selecting admin subscription at simulated time: {e}")
            return all_subscriptions[0]

