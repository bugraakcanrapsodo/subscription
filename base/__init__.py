"""
Base infrastructure components for Stripe subscription testing.
Reused and adapted from PRO 2.0 mobile automation framework.

REUSED FROM PRO 2.0:
- Logger (adapted - removed Appium dependencies)
- XrayApi (used as-is)
- StepTracker (used as-is)

TODO: Implement new components:
- BaseAPIClient: Generic HTTP client with retry logic
- StripeAPIClient: Stripe-specific API client
"""

from .logger import Logger
from .xray_api import XrayApi, UpdateStrategy
from .step_tracker import (
    StepTracker,
    XRayStepTracker,
    XRayTestCollector,
    StepResult
)

__all__ = [
    'Logger',
    'XrayApi',
    'UpdateStrategy',
    'StepTracker',
    'XRayStepTracker',
    'XRayTestCollector',
    'StepResult'
]
