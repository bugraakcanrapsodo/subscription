"""
Subscription State Manager
Centralized logic for capturing and comparing subscription state
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime, timedelta
from base.logger import Logger
from api.mlm_api import MlmAPI
from models.types import SubscriptionState


class SubscriptionStateManager:
    """
    Centralized manager for subscription state operations
    
    This class provides:
    - get_current_state(): Capture subscription state from API
    - verify_states_are_same(): Verify two subscription states match
    
    Used by Executor, Verifiers, and Actions to ensure consistency
    """
    
    def __init__(self, mlm_api: MlmAPI):
        """
        Initialize state manager
        
        Args:
            mlm_api: MLM API client instance
        """
        self.mlm_api = mlm_api
        self.logger = Logger(__name__)
        
        # Load subscription configurations for status mapping
        subscriptions_path = Path(__file__).parent.parent / 'config' / 'subscriptions.json'
        with open(subscriptions_path, 'r') as f:
            self.subscriptions_config = json.load(f)
    
    def get_current_state(self, days_advanced: int = 0) -> SubscriptionState:
        """
        Capture current subscription state from API
        
        Args:
            days_advanced: Days advanced via advance_time (for selecting correct subscription)
        
        Returns:
            SubscriptionState object with current subscription details or free user state
        """
        try:
            subscriptions_response = self.mlm_api.get_subscriptions()
            
            if subscriptions_response.has_active_subscription():
                # Use time-aware selection if days_advanced > 0
                latest_sub = self._select_subscription_at_simulated_time(
                    subscriptions_response,
                    days_advanced
                )
                
                # Get status name from mapping
                status_codes = self.subscriptions_config.get('status_codes', {})
                status_name = status_codes.get(str(latest_sub.status), 'unknown')
                
                # Extract trial period days if present
                trial_period_days = getattr(latest_sub.data.package, 'trial_period_days', None)
                if trial_period_days:
                    trial_period_days = int(trial_period_days)
                
                state = SubscriptionState(
                    exists=True,
                    subscription_id=latest_sub.id,
                    subscription_type=None,  # Set from action config during execution
                    subscription_type_code=latest_sub.type,  # Capture type code from API
                    plan_code=latest_sub.data.package.code,
                    duration_months=None,  # Set from action config during execution
                    status_code=latest_sub.status,
                    status_name=status_name,
                    start_date=latest_sub.startDate,
                    expire_date=latest_sub.expireDate,
                    trial_period_days=trial_period_days,
                    is_cancelled=latest_sub.status == 4,  # Status 4 = cancelled
                    days_advanced=days_advanced
                )
                
                self.logger.debug(
                    f"Captured subscription state: ID={state.subscription_id}, "
                    f"status={state.status_name}, plan={state.plan_code}"
                )
                
            else:
                # Free user - no subscription
                state = SubscriptionState(
                    exists=False,
                    subscription_id=None,
                    subscription_type=None,
                    subscription_type_code=None,
                    plan_code=None,
                    duration_months=None,
                    status_code=None,
                    status_name='free',
                    start_date=None,
                    expire_date=None,
                    trial_period_days=None,
                    is_cancelled=False,
                    days_advanced=days_advanced
                )
                
                self.logger.debug("Captured subscription state: free user (no subscription)")
            
            return state
        
        except Exception as e:
            self.logger.error(f"Error capturing subscription state: {e}")
            return SubscriptionState(
                exists=False,
                subscription_id=None,
                subscription_type=None,
                subscription_type_code=None,
                plan_code=None,
                duration_months=None,
                status_code=None,
                status_name='error',
                start_date=None,
                expire_date=None,
                trial_period_days=None,
                is_cancelled=False,
                days_advanced=days_advanced,
                error=str(e)
            )
    
    def _select_subscription_at_simulated_time(
        self,
        subscriptions_response: Any,
        days_advanced: int = 0
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
            days_advanced: Total days advanced via advance_time actions
            
        Returns:
            The subscription that is active at the simulated time
        """
        all_subs = subscriptions_response.subscriptions
        
        # If no time advancement, use default behavior (latest subscription)
        if days_advanced == 0 or len(all_subs) == 1:
            return subscriptions_response.get_latest_subscription()
        
        # Time has been advanced - need to find the subscription active at simulated time
        self.logger.info(f"Time advanced by {days_advanced} days, selecting subscription at simulated time")
        self.logger.info(f"Found {len(all_subs)} subscription(s) in API response")
        
        try:
            # Get the FIRST (original) subscription's start date as reference
            # Note: API returns subscriptions in order, first is oldest
            original_sub = all_subs[-1]  # Last in list is the oldest
            original_start = datetime.fromisoformat(original_sub.startDate.replace('Z', '+00:00'))
            
            # Calculate simulated current time
            simulated_now = original_start + timedelta(days=days_advanced)
            
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
    
    def verify_states_are_same(
        self,
        state_before: SubscriptionState,
        state_after: SubscriptionState,
        fields_to_verify: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Verify two subscription states are the same
        
        Args:
            state_before: State before action
            state_after: State after action
            fields_to_verify: Specific fields to verify (None = verify all key fields)
            
        Returns:
            Dictionary with verification results:
            - verified (bool): Whether all fields match
            - message (str): Human-readable message
            - checks (dict): Per-field verification results
            - differences (list): List of field names that differ (if any)
        """
        if fields_to_verify is None:
            # Default: verify key subscription fields
            fields_to_verify = [
                'exists',
                'subscription_id',
                'plan_code',
                'status_code',
                'start_date',
                'expire_date'
            ]
        
        checks = {}
        differences = []
        
        for field in fields_to_verify:
            before_val = getattr(state_before, field, None)
            after_val = getattr(state_after, field, None)
            match = before_val == after_val
            
            checks[field] = {
                'passed': match,
                'expected': before_val,
                'actual': after_val,
                'message': 'unchanged' if match else f'changed: {before_val} → {after_val}'
            }
            
            if not match:
                differences.append(field)
                self.logger.warning(f"State difference in '{field}': {before_val} → {after_val}")
        
        # Build result
        verified = len(differences) == 0
        
        if verified:
            if state_before.exists:
                message = f"Subscription state unchanged (ID={state_after.subscription_id})"
            else:
                message = "User remains free (no subscription created)"
            
            self.logger.info(f"✓ {message}")
        else:
            message = f"Subscription state changed: {', '.join(differences)}"
            self.logger.error(f"✗ {message}")
        
        return {
            'verified': verified,
            'message': message,
            'checks': checks,
            'differences': differences if differences else []
        }
