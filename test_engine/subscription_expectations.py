"""
Subscription Expectations Calculator
Centralized logic for calculating expected subscription states, dates, and status codes
"""

import json
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from base.logger import Logger
from models.types import SubscriptionState


class SubscriptionExpectations:
    """
    Centralized calculator for expected subscription values
    
    This class consolidates all logic for calculating:
    - Expected status codes (trial, active, cancelled, expired)
    - Expected dates (start and expire dates)
    - Expected plan codes
    - Expected trial periods
    
    Used by both UserVerifier and AdminVerifier to ensure consistency
    """
    
    def __init__(self, trial_eligible: bool = True):
        """
        Initialize expectations calculator
        
        Args:
            trial_eligible: Whether user is trial eligible
        """
        self.trial_eligible = trial_eligible
        self.logger = Logger(__name__)
        
        # Load subscription configurations
        subscriptions_path = Path(__file__).parent.parent / 'config' / 'subscriptions.json'
        with open(subscriptions_path, 'r') as f:
            self.subscriptions_config = json.load(f)
    
    def calculate_expected_status(
        self,
        action_type: str,
        subscription_type: str,
        subscription_state: Optional[SubscriptionState] = None,
        subscription_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Calculate expected status code and related info based on action type
        
        Args:
            action_type: Type of action (purchase, cancel, refund, reactivate, advance_time)
            subscription_type: Subscription type (1y_premium, 2y_premium, etc)
            subscription_state: Current subscription state
            subscription_config: Subscription configuration
            
        Returns:
            Dict with expected_status_code, expected_status_name, check_trial_period, trial_duration_days
        """
        if subscription_config is None:
            subscription_config = self.subscriptions_config.get(subscription_type, {})
        
        # CANCEL action
        if action_type == 'cancel':
            return {
                'expected_status_code': 4,
                'expected_status_name': 'cancelled',
                'check_trial_period': False,
                'trial_duration_days': None
            }
        
        # REFUND action
        if action_type == 'refund':
            return {
                'expected_status_code': 5,
                'expected_status_name': 'refunded',
                'check_trial_period': False,
                'trial_duration_days': None
            }
        
        # ADVANCE_TIME action
        if action_type == 'advance_time':
            return self._calculate_status_after_time_advance(
                subscription_state=subscription_state,
                subscription_config=subscription_config
            )
        
        # REACTIVATE or PURCHASE actions
        # Both use the same logic: check trial eligibility
        supports_trial = subscription_config.get('supports_trial', False)
        
        if supports_trial and self.trial_eligible:
            # User IS trial eligible and plan supports trial
            return {
                'expected_status_code': subscription_config.get('expected_status_with_trial', 3),
                'expected_status_name': subscription_config.get('expected_status_name_with_trial', 'trial'),
                'check_trial_period': True,
                'trial_duration_days': subscription_config.get('trial_period_days', 45)
            }
        else:
            # User is NOT trial eligible OR plan doesn't support trial
            return {
                'expected_status_code': subscription_config.get('expected_status_without_trial', 1),
                'expected_status_name': subscription_config.get('expected_status_name_without_trial', 'active'),
                'check_trial_period': False,
                'trial_duration_days': None
            }
    
    def calculate_expected_dates(
        self,
        action_type: str,
        subscription_state: Optional[SubscriptionState],
        actual_start_date: str,
        actual_expire_date: str,
        subscription_config: Dict[str, Any]
    ) -> Tuple[str, str]:
        """
        Calculate expected start and expire dates
        
        IMPORTANT: This method uses calendar-based date arithmetic (not fixed day counts)
        to properly handle leap years. Stripe uses calendar years, so we must match.

        Args:
            action_type: Type of action (purchase, cancel, refund, reactivate, advance_time)
            subscription_state: Current subscription state (contains ORIGINAL dates from purchase)
            actual_start_date: Actual start date from API (may be RENEWED subscription)
            actual_expire_date: Actual expire date from API (may be RENEWED subscription)
            subscription_config: Subscription configuration
            
        Returns:
            Tuple of (expected_start_date, expected_expire_date)
        """
        # For purchase/cancel/refund/reactivate: expect actual dates
        if action_type in ['purchase', 'cancel', 'refund', 'reactivate']:
            return (actual_start_date, actual_expire_date)
        
        # For advance_time: calculate based on cancellation state
        if action_type == 'advance_time':
            is_cancelled = subscription_state.is_cancelled if subscription_state else False
            days_advanced = subscription_state.days_advanced if subscription_state else 0
            duration_months = subscription_config.get('duration_months', 12) if subscription_config else 12
            
            self.logger.info(f"Calculating expected dates for advance_time:")
            self.logger.info(f"  is_cancelled: {is_cancelled}")
            self.logger.info(f"  days_advanced: {days_advanced}")
            self.logger.info(f"  duration_months: {duration_months}")
            
            # If cancelled: dates stay unchanged
            if is_cancelled:
                self.logger.info("  → Subscription is CANCELLED - dates remain UNCHANGED")
                return (actual_start_date, actual_expire_date)
            
            # If not cancelled: check if time passed expiration
            # CRITICAL: Use ORIGINAL dates from subscription_state, NOT actual dates from API
            # The API returns the RENEWED subscription's dates after auto-renewal
            try:
                # Get ORIGINAL dates from subscription_state (stored at purchase time)
                original_start_str = subscription_state.start_date if subscription_state else None
                original_expire_str = subscription_state.expire_date if subscription_state else None

                if not original_start_str or not original_expire_str:
                    self.logger.warning("  Missing original dates in subscription_state, using actual dates")
                    start_date = datetime.fromisoformat(actual_start_date.replace('Z', '+00:00'))
                    expire_date = datetime.fromisoformat(actual_expire_date.replace('Z', '+00:00'))
                else:
                    # Use ORIGINAL dates to calculate simulated time
                    start_date = datetime.fromisoformat(original_start_str.replace('Z', '+00:00'))
                    expire_date = datetime.fromisoformat(original_expire_str.replace('Z', '+00:00'))
                    self.logger.info(f"  Using ORIGINAL dates from state: start={original_start_str}, expire={original_expire_str}")

                # Calculate simulated current time from ORIGINAL start date
                simulated_now = start_date + timedelta(days=days_advanced)
                
                self.logger.info(f"  Original Start: {start_date}")
                self.logger.info(f"  Original Expire: {expire_date}")
                self.logger.info(f"  Simulated now: {simulated_now}")

                if simulated_now >= expire_date:
                    # Past expiration - new subscription should start
                    # New subscription starts at OLD expire date
                    expected_start = expire_date
                    
                    # CRITICAL: Use calendar-based arithmetic to handle leap years and varying month lengths
                    # Stripe adds N calendar months/years, not fixed day counts
                    expected_expire = self._add_subscription_duration(
                        start_date=expected_start,
                        duration_months=duration_months
                    )

                    exp_start_str = expected_start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    exp_expire_str = expected_expire.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                    
                    self.logger.info(f"  → Time past expiration - NEW subscription expected")
                    self.logger.info(f"     Expected Start: {exp_start_str}")
                    self.logger.info(f"     Expected Expire: {exp_expire_str}")
                    self.logger.info(f"     (Using calendar math to handle leap years)")

                    return (exp_start_str, exp_expire_str)
                else:
                    # Still within period - dates unchanged
                    self.logger.info("  → Still within period - dates UNCHANGED")
                    return (actual_start_date, actual_expire_date)
                    
            except Exception as e:
                self.logger.warning(f"Error calculating dates: {e}")
                return (actual_start_date, actual_expire_date)
        
        # Default: return actual dates
        return (actual_start_date, actual_expire_date)
    
    def _add_subscription_duration(
        self,
        start_date: datetime,
        duration_months: int
    ) -> datetime:
        """
        Add subscription duration to start date using calendar-based arithmetic.

        This properly handles leap years and varying month lengths by using relativedelta 
        instead of fixed day counts. Stripe uses calendar months (e.g., "12 months from now"), 
        not fixed day counts, which correctly handles February, leap years, and months with 
        different day counts.

        Args:
            start_date: Starting date
            duration_months: Duration in months (12, 24, 120, etc.)

        Returns:
            Expire date calculated using calendar math
        """
        # Use relativedelta for proper calendar arithmetic
        # This handles:
        # - Varying month lengths (28-31 days)
        # - Leap years
        # - Calendar year boundaries
        expire_date = start_date + relativedelta(months=duration_months)

        # Convert months to human-readable format for logging
        if duration_months == 12:
            duration_desc = "1 year"
        elif duration_months == 24:
            duration_desc = "2 years"
        elif duration_months % 12 == 0:
            years = duration_months // 12
            duration_desc = f"{years} years"
        else:
            duration_desc = f"{duration_months} months"

        self.logger.info(f"  Added {duration_desc} ({duration_months} months) to {start_date.date()} → {expire_date.date()}")

        return expire_date

    def get_expected_duration_months(
        self,
        subscription_type: str = None,
        subscription_config: Dict[str, Any] = None
    ) -> int:
        """
        Get expected duration in months for a subscription type

        Args:
            subscription_type: Subscription type (1y_premium, 2y_premium, lifetime, etc)
            subscription_config: Subscription configuration (optional)

        Returns:
            Expected duration in months (120 for lifetime = 10 years)
        """
        if subscription_config is None and subscription_type:
            subscription_config = self.subscriptions_config.get(subscription_type, {})

        if subscription_config:
            return subscription_config.get('duration_months', 12)

        return 12  # Default to 1 year
    
    def _calculate_status_after_time_advance(
        self,
        subscription_state: Optional[SubscriptionState],
        subscription_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate expected status after time advancement
        
        Args:
            subscription_state: Current subscription state
            subscription_config: Subscription configuration
            
        Returns:
            Dict with expected_status_code, expected_status_name, check_trial_period, trial_duration_days
        """
        if not subscription_state:
            # Fallback if no state provided
            return {
                'expected_status_code': 1,
                'expected_status_name': 'active',
                'check_trial_period': False,
                'trial_duration_days': None
            }
        
        days_advanced = subscription_state.days_advanced
        current_status = subscription_state.status_code
        is_cancelled = subscription_state.is_cancelled
        trial_period_days = subscription_state.trial_period_days
        
        self.logger.info(f"Calculating expected status after {days_advanced} days advancement")
        self.logger.info(f"  Current: status={current_status}, cancelled={is_cancelled}, trial_days={trial_period_days}")
        
        try:
            if subscription_state.start_date and subscription_state.expire_date:
                start_date = datetime.fromisoformat(subscription_state.start_date.replace('Z', '+00:00'))
                expire_date = datetime.fromisoformat(subscription_state.expire_date.replace('Z', '+00:00'))
                simulated_now = start_date + timedelta(days=days_advanced)
                
                if simulated_now >= expire_date:
                    # Past expiration
                    if is_cancelled:
                        # Cancelled stays cancelled
                        return {
                            'expected_status_code': 4,
                            'expected_status_name': 'cancelled',
                            'check_trial_period': False,
                            'trial_duration_days': None
                        }
                    else:
                        # Trial expired → new active subscription
                        if trial_period_days and current_status == 3:
                            return {
                                'expected_status_code': 1,
                                'expected_status_name': 'active',
                                'check_trial_period': False,
                                'trial_duration_days': None
                            }
                        else:
                            # Regular active subscription
                            return {
                                'expected_status_code': 1,
                                'expected_status_name': 'active',
                                'check_trial_period': False,
                                'trial_duration_days': None
                            }
                else:
                    # Not yet expired - status unchanged
                    if is_cancelled:
                        return {
                            'expected_status_code': 4,
                            'expected_status_name': 'cancelled',
                            'check_trial_period': False,
                            'trial_duration_days': None
                        }
                    elif trial_period_days and current_status == 3:
                        return {
                            'expected_status_code': 3,
                            'expected_status_name': 'trial',
                            'check_trial_period': True,
                            'trial_duration_days': trial_period_days
                        }
                    else:
                        return {
                            'expected_status_code': 1,
                            'expected_status_name': 'active',
                            'check_trial_period': False,
                            'trial_duration_days': None
                        }
        except Exception as e:
            self.logger.error(f"Error calculating status: {e}")
        
        # Fallback
        return {
            'expected_status_code': current_status or 1,
            'expected_status_name': 'active',
            'check_trial_period': False,
            'trial_duration_days': None
        }