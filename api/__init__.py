"""
API Module
Provides API clients for test automation

This module contains API clients that wrap backend API calls for:
- User authentication (register, login, verification)
- User operations (profile, device registration)
- Subscription management (web plans, create, cancel, reactivate)
- Device registration
- Awesome Golf licenses
- Plan management

Each API client inherits from BaseAPIClient and provides typed methods
for specific API endpoints.
"""

from api.base_client import BaseAPIClient, APIResponse
from api.mlm_api import MlmAPI
from api.config import APIConfig

__all__ = [
    'BaseAPIClient',
    'APIResponse',
    'MlmAPI',
    'APIConfig',
]
