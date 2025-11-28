"""
Subscription Models
Pydantic models for subscription-related API responses
"""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class CurrencyOption(BaseModel):
    """Currency option details"""
    custom_unit_amount: Optional[int] = None
    tax_behavior: str
    unit_amount: int
    unit_amount_decimal: str


class AGPromo(BaseModel):
    """AG Promo details"""
    isEligible: bool
    duration: int


class StackInfo(BaseModel):
    """Stack information"""
    isEligible: bool
    reason: Optional[str] = None


class Plan(BaseModel):
    """Subscription plan details"""
    isEligible: bool
    code: int
    reason: Optional[str] = None
    currency: Optional[str] = None
    currency_option: Optional[CurrencyOption] = None
    monthly_payment: Optional[str] = None
    trial_period_days: Optional[int] = None
    ag_promo: Optional[AGPromo] = None
    stack: Optional[StackInfo] = None


class Session(BaseModel):
    """Stripe checkout session"""
    url: str


class CreateWebSubscriptionResponse(BaseModel):
    """Create web subscription API response"""
    success: bool
    session: Session
    
    def is_success(self) -> bool:
        """
        Check if subscription creation was successful
        
        Returns:
            bool: True if successful, False otherwise
        """
        return self.success
    
    def get_checkout_url(self) -> Optional[str]:
        """
        Get Stripe checkout URL if successful
        
        Returns:
            str: Stripe checkout URL or None if failed
        """
        if self.is_success():
            return self.session.url
        return None


class WebPlansResponse(BaseModel):
    """Web plans API response"""
    success: bool
    plans: Dict[str, Plan]
    
    def get_eligible_plans(self):
        """
        Get list of eligible plans with their names, codes, and trial period
        
        Returns:
            list: List of dicts with 'name', 'code', and 'trial_period_days' keys
        """
        eligible = []
        for plan_name, plan_details in self.plans.items():
            if plan_details.isEligible:
                eligible.append({
                    'name': plan_name,
                    'code': plan_details.code,
                    'trial_period_days': plan_details.trial_period_days
                })
        return eligible
    
    def get_plan_by_code(self, code: int) -> Optional[tuple]:
        """
        Get plan name and details by code
        
        Args:
            code: Plan code
            
        Returns:
            tuple: (plan_name, Plan) or None if not found
        """
        for plan_name, plan_details in self.plans.items():
            if plan_details.code == code:
                return (plan_name, plan_details)
        return None


# ==================== Get Subscriptions Models ====================

class SubscriptionPackage(BaseModel):
    """Subscription package details"""
    code: int
    trial_period_days: Optional[str] = None  # Present for trial subscriptions only


class SubscriptionData(BaseModel):
    """Subscription data details"""
    package: SubscriptionPackage


class Subscription(BaseModel):
    """Individual subscription details"""
    id: int
    type: int
    status: int
    data: SubscriptionData
    startDate: str
    expireDate: str


class GetSubscriptionsResponse(BaseModel):
    """Get subscriptions API response"""
    success: bool
    subscriptions: list[Subscription]
    
    def has_active_subscription(self) -> bool:
        """
        Check if there are any active subscriptions
        
        Returns:
            bool: True if there is at least one subscription, False otherwise
        """
        return len(self.subscriptions) > 0
    
    def get_latest_subscription(self) -> Optional[Subscription]:
        """
        Get the most recent subscription (by startDate)
        
        Returns:
            Subscription: Latest subscription or None if no subscriptions
        """
        if not self.subscriptions:
            return None
        
        # Sort by startDate descending and return first
        sorted_subs = sorted(self.subscriptions, key=lambda x: x.startDate, reverse=True)
        return sorted_subs[0]


# ==================== Cancel/Reactivate Web Subscription Models ====================

class CancelWebSubscriptionResponse(BaseModel):
    """Cancel web subscription API response"""
    success: bool


class ReactivateWebSubscriptionResponse(BaseModel):
    """Reactivate web subscription API response"""
    success: bool


# ==================== AG License Models ====================

class AGLicense(BaseModel):
    """Awesome Golf license details"""
    id: int
    duration: int
    expireDate: str
    createDate: str


class GetAGLicenseResponse(BaseModel):
    """Get AG license API response"""
    success: bool
    license: AGLicense
    
    def is_valid(self) -> bool:
        """
        Check if license retrieval was successful
        
        Returns:
            bool: True if successful, False otherwise
        """
        return self.success
    
    def get_license_info(self) -> Dict[str, Any]:
        """
        Get formatted license information
        
        Returns:
            dict: Dictionary with license details
        """
        return {
            'license_id': self.license.id,
            'duration_months': self.license.duration,
            'expire_date': self.license.expireDate,
            'create_date': self.license.createDate
        }


# ==================== Admin API Models ====================

class AdminSubscription(BaseModel):
    """Admin subscription details"""
    id: int
    userId: int
    email: str
    type: int
    mlmVersion: int
    status: int
    startDate: Optional[str] = None  # Some subscriptions may have None values
    expireDate: Optional[str] = None  # Some subscriptions may have None values
    count: str  # Total count of subscriptions (same for all entries)


class GetAdminSubscriptionsResponse(BaseModel):
    """Get admin subscriptions API response"""
    success: bool
    subscriptions: List[AdminSubscription]
    
    def get_subscription_by_email(self, email: str) -> Optional[AdminSubscription]:
        """
        Find subscription by user email
        
        Args:
            email: User email address
            
        Returns:
            AdminSubscription or None if not found
        """
        for sub in self.subscriptions:
            if sub.email.lower() == email.lower():
                return sub
        return None
    
    def get_subscriptions_by_user_id(self, user_id: int) -> List[AdminSubscription]:
        """
        Get all subscriptions for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of subscriptions for the user
        """
        return [sub for sub in self.subscriptions if sub.userId == user_id]
    
    def get_subscription_by_id(self, subscription_id: int) -> Optional[AdminSubscription]:
        """
        Find subscription by subscription ID
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            AdminSubscription or None if not found
        """
        for sub in self.subscriptions:
            if sub.id == subscription_id:
                return sub
        return None

