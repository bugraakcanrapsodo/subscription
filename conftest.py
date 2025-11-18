"""
Pytest configuration and fixtures for Stripe subscription testing.
Adapted from PRO 2.0 mobile automation framework.

REUSED FROM PRO 2.0:
- setup_logger fixture
- xray_test_collection fixture (structure)
- step_tracker fixture
- init_error_collection fixture

REMOVED FROM PRO 2.0:
- setup_data (Appium driver)
- Mobile-specific fixtures (wifi_manager, file_manager, app_manager, etc.)

TODO: Implement new fixtures:
- stripe_service: Stripe API service fixture
- backend_service: Backend API service fixture
- playwright_service: Playwright service fixture
- cleanup_stripe_resources: Resource cleanup fixture
"""

import pytest
import os
from base.logger import Logger
from base.xray_api import XrayApi, UpdateStrategy
from base.step_tracker import XRayStepTracker, XRayTestCollector


# ==================== Pytest Configuration ====================

def pytest_addoption(parser):
    """Add custom command line options"""
    
    parser.addoption(
        "--xray-enable", action="store_true", default=False,
        help="Enable XRay integration"
    )
    
    parser.addoption(
        "--log-path", action="store", default="logs",
        help="Log directory"
    )
    parser.addoption(
        "--file-log-level", action="store", default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="File log level"
    )
    parser.addoption(
        "--console-log-level", action="store", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Console log level"
    )


# ==================== Session-Scoped Fixtures (REUSED FROM PRO 2.0) ====================

@pytest.fixture(scope="session", autouse=True)
def setup_logger(request):
    """Initialize logger - REUSED FROM PRO 2.0"""
    log_path = request.config.getoption("--log-path")
    file_level = request.config.getoption("--file-log-level")
    console_level = request.config.getoption("--console-log-level")
    
    return Logger.get_instance(
        log_path=log_path,
        file_level=file_level,
        console_level=console_level
    )


@pytest.fixture(scope="session")
def test_params(pytestconfig):
    """Session-wide test parameters"""
    return {
        "xray_enable": pytestconfig.getoption("--xray-enable"),
        "stripe_secret_key": os.getenv("STRIPE_SECRET_KEY"),
        "backend_api_url": os.getenv("BACKEND_API_URL"),
        "playwright_service_url": os.getenv("PLAYWRIGHT_SERVICE_URL", "http://localhost:3000")
    }


@pytest.fixture(scope="session", autouse=True)
def xray_test_collection(test_params, request):
    """
    Session-scoped fixture to collect XRay test IDs only from tests that will actually run.
    This runs once before any tests and either:
    1. Reuses existing execution if TEST_EXECUTION_KEY is provided
    2. Creates new XRay test execution with collected tests only
    Auto-runs when XRay is enabled.
    """

    # Check if XRay is enabled via test parameters
    xray_enable = test_params["xray_enable"]
    if not xray_enable:
        Logger.info("XRay integration disabled - skipping test collection")
        return None

    # Early check if execution already exists to avoid unnecessary work
    if XrayApi.get_execution_key() is not None:
        Logger.info("XRay test execution already exists")
        return None

    Logger.debug("Starting XRay test collection from pytest collected items...")

    # Get pytest session and access the already-collected items
    # NOTE: We don't call perform_collect() because that re-collects ALL tests
    # ignoring any marker filters. Instead, we access session.items which contains
    # the filtered items after pytest_collection_modifyitems hook has run.
    session = request.session
    
    # Wait for pytest to finish collection and filtering
    # The items list will be populated after pytest_collection_modifyitems runs
    collected_items = session.items

    Logger.info(f"Pytest collected {len(collected_items)} test items")

    # Extract XRay test IDs from collected items only
    collector = XRayTestCollector()
    all_test_ids = collector.collect_xray_tests_from_pytest_items(collected_items)

    if not all_test_ids:
        Logger.warning("No XRay tests found in collected test items")
        return None

    Logger.info(f"Collected {len(all_test_ids)} unique XRay test IDs from selected tests: {sorted(all_test_ids)}")

    # Get test parameters
    app_name = test_params["app_name"]
    is_prod_testing = test_params["prod_testing"]

    # Authenticate with XRay first (needed for both create and reuse scenarios)
    Logger.debug("Authenticating with XRay...")
    token = XrayApi.authenticate()
    if not token:
        Logger.warning("⚠️  Failed to authenticate with XRay - continuing without XRay integration")
        Logger.warning("Tests will run normally, but results will not be reported to XRay")
        # Continue without XRay integration instead of failing
        return {
            "all_test_ids": all_test_ids,
            "collector": collector,
            "test_mapping": collector.get_test_mapping(),
            "execution_key": None,
            "reused_execution": False,
            "xray_integration_active": False
        }

        # Configure XRay update strategy from environment variable
    strategy_env = os.getenv('XRAY_UPDATE_STRATEGY', 'PASS_WINS').upper().strip()
    try:
        # Flexible parsing - accept various forms of PASS/FAIL/LAST
        if strategy_env in ['PASS', 'PASSED', 'PASS_WINS', 'PASS_WIN']:
            update_strategy = UpdateStrategy.PASS_WINS
        elif strategy_env in ['FAIL', 'FAILED', 'FAIL_WINS', 'FAIL_WIN']:
            update_strategy = UpdateStrategy.FAIL_WINS
        elif strategy_env in ['LAST', 'LAST_WINS', 'LAST_WIN', 'LATEST']:
            update_strategy = UpdateStrategy.LAST_WINS
        else:
            Logger.warning(f"Invalid XRAY_UPDATE_STRATEGY '{strategy_env}'. Valid options: PASS/PASSED/PASS_WINS, FAIL/FAILED/FAIL_WINS, LAST/LAST_WINS. Using default: PASS_WINS")
            update_strategy = UpdateStrategy.PASS_WINS

        XrayApi.set_update_strategy(update_strategy)
        Logger.info(f"XRay update strategy set to: {update_strategy.value} (from env: {os.getenv('XRAY_UPDATE_STRATEGY', 'default')})")
    except Exception as e:
        Logger.warning(f"Failed to set XRay update strategy: {str(e)}. Using default: PASS_WINS")
        XrayApi.set_update_strategy(UpdateStrategy.PASS_WINS)

    # Check if we should reuse an existing test execution
    existing_execution_key = os.getenv('TEST_EXECUTION_KEY')
    execution_key = None

    if existing_execution_key and existing_execution_key.strip():
        Logger.info(f"TEST_EXECUTION_KEY found: {existing_execution_key.strip()}")

        # Try to reuse the existing execution
        execution_key = XrayApi._reuse_existing_execution(existing_execution_key.strip(), all_test_ids)

        if execution_key:
            Logger.info(f"✓ Successfully reusing existing XRay test execution: {execution_key}")
        else:
            Logger.warning(f"Failed to reuse existing execution {existing_execution_key.strip()}, will create new execution")

    # If no existing execution key provided, or reuse failed, create new execution
    if not execution_key:
        # Get test plan key from environment variable (required for new execution)
        test_plan_key = os.getenv('TEST_PLAN_KEY')
        if not test_plan_key:
            Logger.warning("⚠️  TEST_PLAN_KEY environment variable not found - continuing without XRay integration")
            Logger.warning("Tests will run normally, but results will not be reported to XRay")
            # Continue without XRay integration instead of failing
            return {
                "all_test_ids": all_test_ids,
                "collector": collector,
                "test_mapping": collector.get_test_mapping(),
                "execution_key": None,
                "reused_execution": False,
                "xray_integration_active": False
            }

        # Create XRay test execution with all collected tests
        Logger.debug("Creating new XRay test execution...")
        execution_key = XrayApi.create_test_execution(
            test_ids=all_test_ids,
            test_plan_key=test_plan_key)

        if execution_key:
            Logger.info(f"✓ XRay test execution created successfully: {execution_key}")
        else:
            Logger.warning("⚠️  Failed to create XRay test execution - continuing without XRay integration")
            Logger.warning("Tests will run normally, but results will not be reported to XRay")
            # Continue without XRay integration instead of failing
            execution_key = None

    return {
        "all_test_ids": all_test_ids,
        "collector": collector,
        "test_mapping": collector.get_test_mapping(),
        "execution_key": execution_key,  # Can be None if creation failed
        "reused_execution": bool(existing_execution_key and existing_execution_key.strip()),
        "xray_integration_active": execution_key is not None  # Flag to indicate if XRay is working
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


