"""
Test Fixtures
Provides reusable fixtures for all tests
"""

import os
import pytest
from datetime import datetime
from api.mlm_api import MlmAPI
from base.logger import Logger
from base.xray_api import XrayApi
from base.step_tracker import XRayStepTracker


@pytest.fixture
def mlm_api():
    """Fixture to create MlmAPI client"""
    return MlmAPI()


@pytest.fixture
def test_user_email():
    """Fixture to generate unique test user email with @rapsodotest.com"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"automation_user_{timestamp}@rapsodotest.com"


@pytest.fixture
def registered_user(mlm_api, test_user_email):
    """
    Fixture to create and return a registered user with login token
    
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

