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
        check_dates: bool = False
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
            
            # Find user's subscription
            admin_sub = admin_subs.get_subscription_by_email(user_email)
            
            if not admin_sub:
                self.logger.info(f"No subscription found in admin panel for {user_email} (may be expected for free/cancelled users)")
                return {
                    'verified': False,
                    'message': f'Subscription not found in admin panel for {user_email}',
                    'admin_subscription': None
                }
            
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
            
            # Calculate trial period from dates if status is trial (3)
            trial_period_days = None
            if actual_status_code == 3 and admin_sub.startDate and admin_sub.expireDate:
                try:
                    start_date = datetime.fromisoformat(admin_sub.startDate.replace('Z', '+00:00'))
                    expire_date = datetime.fromisoformat(admin_sub.expireDate.replace('Z', '+00:00'))
                    trial_period_days = (expire_date - start_date).days
                    self.logger.info(f"  Trial Period: {trial_period_days} days (calculated from dates)")
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
                    
                    # Check that start date is recent (within last hour)
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

