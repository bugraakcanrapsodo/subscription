"""
Test Fixtures
Provides reusable fixtures for all tests

ARCHITECTURE NOTE:
- All pytest fixtures are defined HERE (single source of truth)
- Fixtures are imported in conftest.py via "from fixtures import *"
- Test classes (TestExecutor, ActionExecutor, etc.) are regular Python classes
- They receive dependencies (mlm_api, playwright_service_url) via constructor
  because they CANNOT directly access pytest fixtures
- Only test FUNCTIONS (not classes) can use pytest fixtures via parameters
"""

import os
import pytest
from datetime import datetime
from api.mlm_api import MlmAPI
from test_engine.executor import TestExecutor
from base.logger import Logger
from base.xray_api import XrayApi
from base.step_tracker import XRayStepTracker


# ==================== API Fixtures ====================

@pytest.fixture(scope="session")
def mlm_api():
    """Fixture to create MlmAPI client (session-scoped for data-driven tests)"""
    return MlmAPI(env='test')


# ==================== Data-Driven Test Fixtures ====================

@pytest.fixture(scope="session")
def test_config(pytestconfig):
    """Get test configuration from command line options"""
    return {
        'excel_file': pytestconfig.getoption("--excel"),
        'test_id': pytestconfig.getoption("--test-id"),
        'test_tag': pytestconfig.getoption("--test-tag"),
        'playwright_url': pytestconfig.getoption("--playwright-url"),
        'cleanup_users': pytestconfig.getoption("--cleanup-users")
    }


@pytest.fixture(scope="session")
def test_executor(mlm_api, test_config):
    """
    Create test executor for data-driven tests
    
    Note: TestExecutor is a regular Python class, not a pytest test.
    It needs mlm_api and playwright_service_url passed to its constructor
    because it can't directly access pytest fixtures.
    """
    executor = TestExecutor(
        mlm_api=mlm_api,
        playwright_service_url=test_config['playwright_url'],
        cleanup_users=test_config['cleanup_users']
    )
    return executor


# ==================== User Setup Fixtures ====================


@pytest.fixture
def test_user_email():
    """Fixture to generate unique test user email with @rapsodotest.com"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"automation_user_{timestamp}@rapsodotest.com"


@pytest.fixture
def registered_user(mlm_api, test_user_email):
    """
    Fixture to create and return a registered user with login token
    Note: Does NOT register device - use trial_active_user or trial_inactive_user for that
    
    Returns:
        dict: {
            'email': str,
            'password': str,
            'user_data': dict (from registration),
            'token': str (from login),
            'mlm_api': MlmAPI (authenticated client)
        }
    """
    # Register user with default password
    register_response = mlm_api.register(email=test_user_email)
    
    if not register_response.is_success():
        pytest.fail(f"Failed to register user: {register_response.message}")
    
    # Login to get token
    login_response = mlm_api.login(email=test_user_email, password="Aa123456")
    
    if not login_response.is_success():
        pytest.fail(f"Failed to login user: {login_response.message}")
    
    return {
        'email': test_user_email,
        'password': "Aa123456",
        'user_data': register_response.data,
        'token': login_response.data['token'],
        'mlm_api': mlm_api
    }


@pytest.fixture
def trial_active_user(mlm_api, test_user_email):
    """
    Fixture to create a user with ACTIVE trial status (trial eligible)
    
    Trial eligibility is determined by device serial number:
    - NEW/UNIQUE serial number → Trial eligible
    
    Trial periods by plan:
    - 1y_premium: 45 days trial
    - 2y_premium: 45 days trial
    - 1y_platinum: 30 days trial
    
    Returns:
        dict: {
            'email': str,
            'password': str,
            'user_data': dict,
            'token': str,
            'mlm_api': MlmAPI,
            'device_serial': str (unique serial),
            'trial_status': str ('Active')
        }
    """
    logger = Logger(__name__)
    
    # Register user
    register_response = mlm_api.register(email=test_user_email)
    
    if not register_response.is_success():
        pytest.fail(f"Failed to register user: {register_response.message}")
    
    # Login
    login_response = mlm_api.login(email=test_user_email, password="Aa123456")
    
    if not login_response.is_success():
        pytest.fail(f"Failed to login user: {login_response.message}")
    
    # Register device with UNIQUE serial number (trial eligible)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_serial = f"M2P{timestamp}"  # Unique serial based on timestamp
    unique_mac = f"AA:BB:CC:DD:EE:{datetime.now().strftime('%S')}"
    
    device_response = mlm_api.register_device(
        registered_mac=unique_mac,
        registered_serial=unique_serial
    )
    
    if not device_response.is_success():
        logger.warning(f"Device registration failed: {device_response.message}")
    else:
        logger.info(f"Device registered with unique serial: {unique_serial} (TRIAL ELIGIBLE)")
    
    return {
        'email': test_user_email,
        'password': "Aa123456",
        'user_data': register_response.data,
        'token': login_response.data['token'],
        'mlm_api': mlm_api,
        'device_serial': unique_serial,
        'trial_status': 'Active'
    }


@pytest.fixture
def trial_inactive_user(mlm_api, test_user_email):
    """
    Fixture to create a user with INACTIVE trial status (NOT trial eligible)
    
    Trial eligibility is determined by device serial number:
    - KNOWN trial serial number → Trial NOT eligible
    
    Uses static serial: "M2P122827570" (known trial device)
    
    Returns:
        dict: {
            'email': str,
            'password': str,
            'user_data': dict,
            'token': str,
            'mlm_api': MlmAPI,
            'device_serial': str (known trial serial),
            'trial_status': str ('None')
        }
    """
    logger = Logger(__name__)
    
    # Register user
    register_response = mlm_api.register(email=test_user_email)
    
    if not register_response.is_success():
        pytest.fail(f"Failed to register user: {register_response.message}")
    
    # Login
    login_response = mlm_api.login(email=test_user_email, password="Aa123456")
    
    if not login_response.is_success():
        pytest.fail(f"Failed to login user: {login_response.message}")
    
    # Register device with KNOWN trial serial (trial NOT eligible)
    known_trial_serial = "M2P122827570"  # Static known trial device
    unique_mac = f"AA:BB:CC:DD:EE:{datetime.now().strftime('%S')}"
    
    device_response = mlm_api.register_device(
        registered_mac=unique_mac,
        registered_serial=known_trial_serial
    )
    
    if not device_response.is_success():
        logger.warning(f"Device registration failed: {device_response.message}")
    else:
        logger.info(f"Device registered with known trial serial: {known_trial_serial} (TRIAL NOT ELIGIBLE)")
    
    return {
        'email': test_user_email,
        'password': "Aa123456",
        'user_data': register_response.data,
        'token': login_response.data['token'],
        'mlm_api': mlm_api,
        'device_serial': known_trial_serial,
        'trial_status': 'None'
    }


# ==================== Function-Scoped Fixtures ====================

@pytest.fixture(scope="function", autouse=True)
def init_error_collection():
    """Initialize error collection for each test."""
    Logger.init_error_collection()
    yield


@pytest.fixture(scope="function")
def step_tracker(request, test_params):
    """
    TestStepTracker fixture with automatic reporting to consolidated CSV.
    Collects results for session-wide ReportPortal attachment.
    """

    tracker = XRayStepTracker()

    # Get test metadata
    test_name = request.node.name
    test_module = request.node.module.__name__ if request.node.module else "unknown"
    test_file = os.path.basename(request.node.fspath) if hasattr(request.node, 'fspath') else "unknown"

    # Add metadata to tracker
    tracker.test_name = test_name
    tracker.test_module = test_module
    tracker.test_file = test_file

    Logger.info(f"Starting test: {test_name}")

    yield tracker

    # This runs after the test completes
    try:
        # Print summary results for this test
        Logger.info(f"\n" + "="*60)
        Logger.info(f"Step Tracker Summary for: {test_name}")
        Logger.info("="*60)

        # Get basic stats
        total_steps = len(tracker.steps)
        passed_steps = len([s for s in tracker.steps if s.result.value == "PASSED"])
        failed_steps = len([s for s in tracker.steps if s.result.value == "FAILED"])
        pending_steps = len([s for s in tracker.steps if s.result.value == "PENDING"])

        Logger.info(f"""Total Steps: {total_steps}
                        Passed Steps: {passed_steps}
                        Failed Steps: {failed_steps}
                        Pending Steps: {pending_steps}""")

        # Step details
        Logger.info("Step Details:")
        for step in tracker.steps:
            status_icon = "✓" if step.result.value == "PASSED" else "✗" if step.result.value == "FAILED" else "?"
            xray_info = f" [XRay: {', '.join([t.test_key for t in step.xray_tests])}]" if step.xray_tests else ""
            Logger.info(f"  {status_icon} Step {step.step_number}: {step.description}{xray_info}")

            # Show sub-steps if any
            if step.sub_steps:
                for sub_step in step.sub_steps:
                    sub_icon = "✓" if sub_step.result.value == "PASSED" else "✗"
                    Logger.info(f"    {sub_icon} {sub_step.description}")

        # XRay results summary
        xray_results = tracker.get_xray_test_results()
        if xray_results:
            Logger.debug("XRay Test Results:")
            for test_key, result in xray_results.items():
                status_icon = "✓" if result == "PASSED" else "✗" if result == "FAILED" else "?"
                Logger.debug(f"  {status_icon} {test_key}: {result}")

            # Update XRay test run status only if XRay is enabled and working
            if test_params["xray_enable"] and XrayApi.get_execution_key():
                Logger.debug("Updating XRay test run status...")
                success = XrayApi.update_test_run_status(xray_results)
                if success:
                    Logger.debug("✓ XRay test run status updated successfully")
                else:
                    Logger.warning("✗ Failed to update XRay test run status")
            elif test_params["xray_enable"]:
                Logger.warning("XRay enabled but no execution key available - skipping test run status update")
            else:
                Logger.info("XRay integration disabled - skipping test run status update")

        Logger.info("="*60)

    except Exception as e:
        Logger.error(f"Failed to generate test summary: {str(e)}")

