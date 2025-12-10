"""
Internal Types
Enums and dataclasses for framework-internal data structures
"""

from enum import Enum
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field


# ==================== Framework Enums ====================

class ActionType(Enum):
    """Test action types defined in framework"""
    PURCHASE = "purchase"
    CANCEL = "cancel"
    REACTIVATE = "reactivate"
    ADVANCE_TIME = "advance_time"
    VERIFY = "verify"
    REFUND = "refund"


class CleanupMode(Enum):
    """User cleanup modes for test execution"""
    NEVER = "never"
    PASSED = "passed"
    ALWAYS = "always"


class VerificationType(Enum):
    """Types of verification performed"""
    USER_API = "user_api"
    ADMIN_API = "admin_api"
    STRIPE_CHECKOUT = "stripe_checkout"
    MANUAL = "manual"


class ExpectedPaymentResult(Enum):
    """Expected result for payment actions"""
    SUCCESS = "success"
    DECLINED = "declined"


class TestStatus(Enum):
    """Test execution status"""
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


# ==================== Dataclasses ====================

@dataclass
class SubscriptionState:
    """
    Subscription state captured from API or tracked during test execution
    
    This is the single source of truth for subscription state across the framework.
    Status codes and type codes are kept as integers matching the API/config values.
    """
    # Core subscription data
    exists: bool
    subscription_id: Optional[str] = None
    subscription_type: Optional[str] = None  # e.g., '1y_premium', '2y_premium' (from config)
    subscription_type_code: Optional[int] = None  # 1=in-app, 2=web, 3=promotion (from API)
    plan_code: Optional[int] = None
    duration_months: Optional[int] = None
    status_code: Optional[int] = None  # 1=active, 3=trial, 4=cancelled, etc (from config)
    status_name: str = 'free'
    start_date: Optional[str] = None
    expire_date: Optional[str] = None
    trial_period_days: Optional[int] = None
    
    # Test execution tracking
    is_cancelled: bool = False
    days_advanced: int = 0
    
    # Optional metadata
    test_name: Optional[str] = None
    error: Optional[str] = None


@dataclass
class VerificationCheck:
    """Individual verification check result"""
    passed: bool
    expected: Any
    actual: Any
    message: str


@dataclass
class VerificationResult:
    """Result of a verification operation"""
    verified: bool
    message: str
    verification_type: VerificationType
    action_name: Optional[str] = None
    checks: Dict[str, VerificationCheck] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)
    subscription: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for test results
        
        Returns:
            Dictionary representation
        """
        result = {
            'verified': self.verified,
            'message': self.message,
            'verification_type': self.verification_type.value,
        }
        
        if self.action_name:
            result['action_name'] = self.action_name
        
        if self.checks:
            result['checks'] = {
                k: {
                    'passed': v.passed,
                    'expected': v.expected,
                    'actual': v.actual,
                    'message': v.message
                } for k, v in self.checks.items()
            }
        
        if self.issues:
            result['issues'] = self.issues
        
        if self.subscription:
            result['subscription'] = self.subscription
        
        return result

