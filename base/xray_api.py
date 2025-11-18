import os
import time
import requests
import json
import re
from datetime import datetime
import pytz
from enum import Enum
from base.logger import Logger


class UpdateStrategy(Enum):
    """Enum for different test result update strategies"""
    PASS_WINS = "PASS_WINS"  # PASS results won't be overwritten by FAIL
    FAIL_WINS = "FAIL_WINS"  # FAIL results won't be overwritten by PASS
    LAST_WINS = "LAST_WINS"  # Always update with the latest result (original behavior)


class XrayApi:

    # Class variables to store authentication and execution info
    _auth_token = None
    _execution_id = None
    _execution_key = None
    _execution_total_tests = None


    # Static variable to track test results across all test executions
    # Format: {test_key: "PASS/FAIL/TODO"}
    _test_results_cache = {}

    # Configuration for update strategy
    _update_strategy = UpdateStrategy.PASS_WINS  # Default to PASS wins behavior

    global today_date
    today_date = datetime.now()

    @classmethod
    def set_update_strategy(cls, strategy: UpdateStrategy):
        """
        Set the update strategy for test results.

        Args:
            strategy: UpdateStrategy enum value
                - PASS_WINS: PASS results won't be overwritten by FAIL
                - FAIL_WINS: FAIL results won't be overwritten by PASS
                - LAST_WINS: Always update with latest result (original behavior)
        """
        cls._update_strategy = strategy
        Logger.info(f"XRay update strategy set to: {strategy.value}")

    @classmethod
    def get_update_strategy(cls):
        """
        Get the current update strategy.

        Returns:
            UpdateStrategy: Current update strategy
        """
        return cls._update_strategy

    @classmethod
    def authenticate(cls):
        """
        Authenticate with XRay using GitLab CI/CD environment variables.
        Stores token as class variable without "Bearer " prefix.

        Returns:
            str: Authentication token (without "Bearer " prefix)
        """
        # If we already have a token, return it
        if cls._auth_token is not None:
            return cls._auth_token

        url = "https://xray.cloud.getxray.app/api/v1/authenticate"
        headers = {
            "Content-Type": "application/json"
        }
        json_input = {
            "client_id": os.getenv('XRAY_CLIENT_ID_BUGRA'),
            "client_secret": os.getenv('XRAY_CLIENT_SECRET_BUGRA')
        }

        response = requests.post(url, json=json_input, headers=headers)
        response.raise_for_status()  # Raises an exception if the request returned an unsuccessful status code

        # Store token as class variable without "Bearer " prefix
        cls._auth_token = response.text.strip('"')  # Remove quotes from the beginning and end

        return cls._auth_token

    @classmethod
    def get_authentication_token(cls):
        """
        Get the current authentication token.

        Returns:
            str: Authentication token (without "Bearer " prefix) or None if not authenticated
        """
        return cls._auth_token

    @classmethod
    def get_execution_id(cls):
        """
        Get the current test execution ID.

        Returns:
            str: Test execution ID or None if no execution created
        """
        return cls._execution_id

    @classmethod
    def get_execution_key(cls):
        """
        Get the current test execution key.

        Returns:
            str: Test execution key or None if no execution created
        """
        return cls._execution_key

    @classmethod
    def get_cached_test_results(cls):
        """
        Get the current cached test results.

        Returns:
            dict: Dictionary of cached test results {test_key: status}
        """
        return cls._test_results_cache.copy()

    @classmethod
    def clear_test_results_cache(cls):
        """
        Clear the cached test results. Useful for testing or new execution cycles.
        """
        cls._test_results_cache.clear()
        Logger.info("Test results cache cleared")

    @classmethod
    def create_test_execution(cls, test_ids, test_plan_key, retry_count=3, retry_delay=5):
        """
        Create XRay test execution with collected test IDs.

        Args:
            test_ids: List of XRay test IDs (e.g., ["RQA-15698", "RQA-18957"])
            test_plan_key: XRay test plan key (e.g., "RQA-12345")
            retry_count: Number of retry attempts
            retry_delay: Delay between retries in seconds

        Returns:
            str: Test execution key if successful, None otherwise
        """

        # Get authentication token
        if cls.get_authentication_token() is None:
            Logger.info("Getting authentication token...")
            cls.authenticate()

        if cls.get_authentication_token() is None:
            Logger.error("Failed to get authentication token. Cannot create test execution.")
            return None

        # Check for invalid test IDs and provide upfront warning
        valid_test_ids = []
        invalid_test_ids = []
        
        xray_pattern = re.compile(r'^[A-Z]+-\d+$')
        
        for test_id in test_ids:
            if test_id and test_id.strip() and xray_pattern.match(test_id.strip()):
                valid_test_ids.append(test_id.strip())
            else:
                invalid_test_ids.append(test_id)
        
        # Show upfront warning for invalid test IDs found during collection
        if invalid_test_ids:
            Logger.warning(f"⚠️  XRay Test Execution Creation: Found {len(invalid_test_ids)} invalid test IDs that will be skipped:")
            for invalid_id in invalid_test_ids:
                Logger.warning(f"   → '{invalid_id}' (expected format: PREFIX-NUMBER, e.g., 'RQA-12345')")
            Logger.warning(f"   Total valid test IDs to be created: {len(valid_test_ids)}")
        
        # Use only valid test IDs for execution creation
        test_ids_to_use = valid_test_ids if valid_test_ids else test_ids

        # Format test IDs with TODO status
        formatted_tests = []
        for test_id in test_ids_to_use:
            formatted_tests.append({
                "testKey": test_id,
                "status": "TODO"
            })

        # Create summary
        summary = f"Automation - Subscription - Test Env - {today_date.strftime('%Y-%m-%d')}"

        # Get current timestamp for startDate
        timezone = pytz.timezone('Etc/GMT-3')
        start_time = datetime.now(timezone).strftime("%Y-%m-%dT%H:%M:%S%z")

        url = "https://xray.cloud.getxray.app/api/v1/import/execution"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.get_authentication_token()}"
        }

        json_input = {
            "info": {
                "summary": summary,
                "description": "This execution is automatically created via REST API during the test automation execution",
                "startDate": start_time,
                "testPlanKey": test_plan_key
            },
            "tests": formatted_tests
        }

        Logger.debug(f"json_input: {json_input}")

        Logger.info(f"""Creating XRay test execution with {len(test_ids_to_use)} tests...
                        Test Plan Key: {test_plan_key}
                        Summary: {summary}""")


        for attempt in range(retry_count):
            try:
                response = requests.post(url, json=json_input, headers=headers)
                response_code = response.status_code
                Logger.debug(f"Attempt {attempt + 1}: Status Code {response_code}")

                if response_code == 200:
                    response_json = response.json()
                    execution_id = response_json.get("id")
                    execution_key = response_json.get("key")

                    # Store both ID and key as class variables
                    cls._execution_id = execution_id
                    cls._execution_key = execution_key

                    # Initialize cache for all valid test IDs with TODO status (not needed for LAST_WINS only)
                    if cls._update_strategy != UpdateStrategy.LAST_WINS:
                        for test_id in test_ids_to_use:
                            if test_id not in cls._test_results_cache:
                                cls._test_results_cache[test_id] = "TODO"

                    Logger.debug(f"""✓ XRay Test execution created successfully:
                                        ID: {execution_id}
                                        Key: {execution_key}
                                        Initialized cache with {len(test_ids_to_use)} tests""")


                    return execution_key
                elif response_code == 400:
                    try:
                        error_response = response.json()
                        error_message = error_response.get("error", "")
                        if "Test Plan" in error_message:
                            Logger.warning(f"Invalid test plan key '{test_plan_key}': {error_message}")
                        else:
                            Logger.warning(f"Bad request (400): {error_message}")
                    except:
                        Logger.warning(f"Bad request (400): {response.text}")
                    break
                elif response_code == 404:
                    Logger.warning(f"Test plan '{test_plan_key}' not found. Please check TEST_PLAN_KEY.")
                    break
                elif response_code == 503:
                    Logger.warning("Service Unavailable, retrying...")
                    time.sleep(retry_delay)
                else:
                    Logger.error(f"Unexpected error: {response_code} - {response.text}")
                    break

            except Exception as e:
                Logger.error(f"Exception during test execution creation: {str(e)}")
                break

        Logger.error("Failed to create test execution after all attempts")
        return None

    @classmethod
    def _should_update_test_result(cls, test_key, new_status):
        """
        Determine if a test result should be updated based on configured strategy.

        Args:
            test_key: XRay test key
            new_status: New status to be set ("PASSED" or "FAILED")

        Returns:
            tuple: (should_update: bool, reason: str)
        """
        # LAST_WINS strategy - always update (original behavior)
        if cls._update_strategy == UpdateStrategy.LAST_WINS:
            return True, f"LAST_WINS strategy: Always update to {new_status}"

        # For other strategies, check cache
        if test_key not in cls._test_results_cache:
            # No previous result, always update
            return True, "No previous result"

        current_status = cls._test_results_cache[test_key]

        Logger.debug(f"current_status: {current_status}, new_status:{new_status}")

        if current_status == "TODO":
            # Always update from TODO
            return True, f"Updating from TODO to {new_status}"

        # PASS_WINS strategy
        if cls._update_strategy == UpdateStrategy.PASS_WINS:
            if current_status == "PASSED":
                if new_status == "PASSED":
                    return False, "Already PASSED, no update needed"
                else:  # new_status == "FAILED"
                    return False, "PASS-wins logic: Not overwriting PASSED with FAILED"

            if current_status == "FAILED":
                if new_status == "PASSED":
                    return True, "PASS-wins logic: Updating FAILED to PASSED"
                else:  # new_status == "FAILED"
                    return False, "Already FAILED, no update needed"

        # FAIL_WINS strategy
        elif cls._update_strategy == UpdateStrategy.FAIL_WINS:
            if current_status == "FAILED":
                if new_status == "FAILED":
                    return False, "Already FAILED, no update needed"
                else:  # new_status == "PASSED"
                    return False, "FAIL-wins logic: Not overwriting FAILED with PASSED"

            if current_status == "PASSED":
                if new_status == "FAILED":
                    return True, "FAIL-wins logic: Updating PASSED to FAILED"
                else:  # new_status == "PASSED"
                    return False, "Already PASSED, no update needed"

        # Default case
        return True, f"Updating {current_status} to {new_status}"


    @classmethod
    def update_test_run_status(cls, test_results):
        """
        Update test run status for multiple tests in XRay execution.

        Behavior depends on configured update strategy:
        - LAST_WINS: Always update with latest result (original behavior)
        - PASS_WINS: PASS results won't be overwritten by FAIL
        - FAIL_WINS: FAIL results won't be overwritten by PASS

        Args:
            test_results: Dict[str, str] mapping test keys to status (e.g., {"RQA-15698": "PASSED", "RQA-18957": "FAILED"})

        Returns:
            bool: True if successful, False otherwise
        """

        # Get execution key from class variable
        execution_key = cls.get_execution_key()
        if not execution_key:
            Logger.error("No execution key found. Cannot update test run status.")
            return False

        # Get authentication token
        if cls.get_authentication_token() is None:
            Logger.error("No authentication token found. Cannot update test run status.")
            return False

        if not test_results:
            Logger.warning("No test results to update.")
            return True

        # If LAST_WINS strategy, skip filtering and update all tests directly
        if cls._update_strategy == UpdateStrategy.LAST_WINS:
            Logger.info(f"Updating {len(test_results)} tests in XRay (LAST_WINS strategy)")
            return cls._update_test_run_status_api(test_results)

        # For other strategies, filter test results based on logic
        tests_to_update = {}
        skipped_tests = {}

        for test_key, new_status in test_results.items():
            should_update, reason = cls._should_update_test_result(test_key, new_status)

            if should_update:
                tests_to_update[test_key] = new_status
                Logger.debug(f"Will update {test_key}: {reason}")
            else:
                skipped_tests[test_key] = new_status
                Logger.debug(f"Skipping {test_key}: {reason}")

        # Update cache for all results
        for test_key, new_status in test_results.items():
            if test_key in tests_to_update:
                # Only update cache if we're actually updating XRay
                cls._test_results_cache[test_key] = new_status

        # Log summary of what will be updated
        if tests_to_update:
            Logger.info(f"Updating {len(tests_to_update)} tests in XRay (skipped {len(skipped_tests)} due to {cls._update_strategy.value} logic)")
            for test_key, status in tests_to_update.items():
                Logger.debug(f"  → {test_key}: {status}")
        else:
            Logger.info(f"No tests need updating in XRay (all {len(skipped_tests)} skipped due to {cls._update_strategy.value} logic)")
            return True

        # Proceed with API update only for tests that need updating
        return cls._update_test_run_status_api(tests_to_update)

    @classmethod
    def _update_test_run_status_api(cls, test_results):
        """
        Internal method to make the actual API call to update test results.

        Args:
            test_results: Dict[str, str] mapping test keys to status

        Returns:
            bool: True if successful, False otherwise
        """
        url = "https://xray.cloud.getxray.app/api/v1/import/execution"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.get_authentication_token()}"
        }

        timezone = pytz.timezone('Etc/GMT-3')
        now = datetime.now(timezone).strftime("%Y-%m-%dT%H:%M:%S%z")

        # Format test results into required structure
        formatted_tests = []
        for test_key, status in test_results.items():
            formatted_tests.append({
                "testKey": test_key,
                "start": now,
                "finish": now,
                "status": status
            })

        json_input = {
            "testExecutionKey": cls.get_execution_key(),
            "info": {
                "finishDate": now
            },
            "tests": formatted_tests
        }

        Logger.debug(f"Updating status for {len(test_results)} tests in execution {cls.get_execution_key()}")
        Logger.debug(f"json_input: {json_input}")

        try:
            response = requests.post(url, json=json_input, headers=headers)
            response_code = response.status_code

            if response_code == 200:
                Logger.info(f"✓ Successfully updated {len(test_results)} test run statuses in XRay")
                return True
            else:
                Logger.error(f"Failed to update test run status: {response_code} - {response.text}")
                return False

        except Exception as e:
            Logger.error(f"Exception during test run status update: {str(e)}")
            return False

    @classmethod
    def get_test_titles(cls, test_keys):
        """
        Get test titles from XRay using GraphQL API.

        Args:
            test_keys: List of XRay test keys (e.g., ["RQA-18957", "RQA-14626"])

        Returns:
            Dict[str, str]: Dictionary mapping test keys to their titles
        """
        if not test_keys:
            Logger.warning("No test keys provided to get_test_titles")
            return {}

        # Get authentication token
        if cls.get_authentication_token() is None:
            Logger.warning("No authentication token found. Cannot get test titles.")
            return {}

        url = "https://xray.cloud.getxray.app/api/v2/graphql"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cls.get_authentication_token()}"
        }

        # Create JQL query string
        test_keys_str = ", ".join(test_keys)
        query = {
            "query": f'''
            {{
              getTests(jql: "key in ({test_keys_str})", limit: 100) {{
                total
                start
                limit
                results {{
                  issueId
                  jira(fields: ["key", "summary"])
                }}
              }}
            }}
            '''
        }

        Logger.debug(f"Fetching titles for {len(test_keys)} XRay tests...")

        try:
            response = requests.post(url, json=query, headers=headers)
            response_code = response.status_code

            if response_code == 200:
                data = response.json()

                # Extract titles from response
                titles = {}
                if "data" in data and "getTests" in data["data"]:
                    results = data["data"]["getTests"].get("results", [])
                    for result in results:
                        jira_info = result.get("jira", {})
                        if jira_info and "key" in jira_info and "summary" in jira_info:
                            titles[jira_info["key"]] = jira_info["summary"]

                Logger.info(f"✓ Successfully fetched {len(titles)} test titles")
                return titles

            else:
                Logger.error(f"Failed to get test titles: {response_code} - {response.text}")
                return {}

        except Exception as e:
            Logger.error(f"Exception during test titles fetch: {str(e)}")
            return {}

    @classmethod
    def _reuse_existing_execution(cls, execution_key, test_ids):
        """
        Reuse an existing test execution instead of creating a new one.

        Args:
            execution_key: Existing test execution key to reuse
            test_ids: List of test IDs (for cache initialization)

        Returns:
            str: Test execution key if successful, None otherwise
        """
        try:
            # Get authentication token
            if cls.get_authentication_token() is None:
                Logger.info("Getting authentication token...")
                cls.authenticate()

            if cls.get_authentication_token() is None:
                Logger.error("Failed to get authentication token. Cannot reuse test execution.")
                return None

            # Verify the execution exists by trying to get its details
            if not cls._verify_execution_exists(execution_key):
                Logger.error(f"Test execution {execution_key} does not exist or is not accessible")
                return None

            # Store the execution key
            cls._execution_key = execution_key

            # Get current test results from the execution (if using caching strategies)
            if cls._update_strategy != UpdateStrategy.LAST_WINS:
                cls._load_existing_test_results(execution_key, test_ids)

            Logger.info(f"""✓ Reusing existing XRay test execution:
                            Key: {execution_key}
                            Strategy: {cls._update_strategy.value}
                            Loaded cache with existing results""")

            return execution_key

        except Exception as e:
            Logger.error(f"Failed to reuse existing test execution {execution_key}: {str(e)}")
            return None


    @classmethod
    def _verify_execution_exists(cls, execution_key):
        """
        Verify that a test execution exists and is accessible.
        Also stores the internal issueId and total test count for later use.

        Args:
            execution_key: Test execution key to verify

        Returns:
            bool: True if execution exists and is accessible
        """
        try:
            url = f"https://xray.cloud.getxray.app/api/v2/graphql"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cls.get_authentication_token()}"
            }

            # Get execution details including issueId and test count
            query = {
                "query": f'''
                {{
                getTestExecutions(jql: "key={execution_key}", limit: 1) {{
                    total
                    start
                    limit
                    results {{
                    issueId
                    jira(fields: ["key", "summary"])
                    projectId
                    tests(limit: 1) {{
                        total
                    }}
                    }}
                }}
                }}
                '''
            }

            response = requests.post(url, json=query, headers=headers)
            response.raise_for_status()

            data = response.json()

            # Check if we found any test executions
            if ("data" in data and
                "getTestExecutions" in data["data"] and
                data["data"]["getTestExecutions"]["total"] > 0):

                results = data["data"]["getTestExecutions"]["results"]
                if results and len(results) > 0:
                    execution_info = results[0]
                    jira_info = execution_info.get("jira", {})
                    issue_id = execution_info.get("issueId")
                    total_tests = execution_info.get("tests", {}).get("total", 0)

                    # Store the internal issueId and test count for later use
                    cls._execution_id = issue_id  # Reuse existing class variable
                    cls._execution_total_tests = total_tests

                    Logger.info(f"Found existing execution: {execution_key} - {jira_info.get('summary', 'No summary')}")
                    Logger.info(f"Internal issueId: {issue_id}, Total tests: {total_tests}")
                    return True

            Logger.warning(f"Test execution {execution_key} not found")
            return False

        except Exception as e:
            Logger.error(f"Error verifying test execution {execution_key}: {str(e)}")
            return False

    @classmethod
    def _load_existing_test_results(cls, execution_key, test_ids):
        """
        Load existing test results from the test execution to populate cache.
        Handles executions with more than 100 tests by paginating through results.

        Args:
            execution_key: Test execution key
            test_ids: List of test IDs to check
        """
        try:
            # Use the stored internal issueId
            if not cls._execution_id:
                Logger.error(f"Internal issueId not found for execution {execution_key}")
                # Fallback: Initialize all as TODO
                for test_id in test_ids:
                    cls._test_results_cache[test_id] = "TODO"
                return

            issue_id = cls._execution_id
            total_tests = getattr(cls, '_execution_total_tests', 0)

            Logger.info(f"Loading test results for execution {execution_key} (issueId: {issue_id}, total tests: {total_tests})")

            url = f"https://xray.cloud.getxray.app/api/v2/graphql"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {cls.get_authentication_token()}"
            }

            loaded_results = {}
            limit = 100  # Maximum limit per request
            start = 0

            # Paginate through all test runs if there are more than 100 tests
            while start < total_tests:
                Logger.debug(f"Loading test runs {start}-{start + limit - 1} of {total_tests}")

                query = {
                    "query": f'''
                    {{
                    getTestExecution(issueId: "{issue_id}") {{
                        issueId
                        jira(fields: ["key"])
                        testRuns(limit: {limit}, start: {start}) {{
                        total
                        start
                        limit
                        results {{
                            id
                            status {{
                            name
                            description
                            }}
                            test {{
                            issueId
                            jira(fields: ["key"])
                            }}
                        }}
                        }}
                    }}
                    }}
                    '''
                }

                response = requests.post(url, json=query, headers=headers)
                response.raise_for_status()

                data = response.json()

                if ("data" in data and
                    "getTestExecution" in data["data"] and
                    data["data"]["getTestExecution"]):

                    test_execution = data["data"]["getTestExecution"]
                    test_runs_data = test_execution.get("testRuns", {})
                    test_runs = test_runs_data.get("results", [])

                    # Process this batch of test runs
                    for test_run in test_runs:
                        test_info = test_run.get("test", {})
                        status_info = test_run.get("status", {})

                        test_jira_info = test_info.get("jira", {})
                        test_key = test_jira_info.get("key")
                        status_name = status_info.get("name")

                        if test_key and status_name:
                            # Map XRay status names to our internal format
                            if status_name.upper() in ["PASS", "PASSED"]:
                                loaded_results[test_key] = "PASSED"
                            elif status_name.upper() in ["FAIL", "FAILED"]:
                                loaded_results[test_key] = "FAILED"
                            else:
                                loaded_results[test_key] = "TODO"

                    # Update pagination
                    actual_returned = len(test_runs)
                    start += actual_returned

                    # Break if we got fewer results than expected (reached the end)
                    if actual_returned < limit:
                        break

                else:
                    Logger.warning(f"No test runs data found in response for execution {execution_key}")
                    break

            # Initialize cache with loaded results
            for test_id in test_ids:
                if test_id in loaded_results:
                    cls._test_results_cache[test_id] = loaded_results[test_id]
                else:
                    # Test not found in execution results, assume TODO
                    cls._test_results_cache[test_id] = "TODO"

            Logger.info(f"Loaded {len(loaded_results)} existing test results from execution {execution_key}")
            Logger.debug(f"cls._test_results_cache: {cls._test_results_cache}")

            # Log summary of loaded results
            result_summary = {"PASSED": 0, "FAILED": 0, "TODO": 0}
            for status in loaded_results.values():
                if status in result_summary:
                    result_summary[status] += 1

            Logger.info(f"Existing results summary: {result_summary['PASSED']} PASSED, {result_summary['FAILED']} FAILED, {result_summary['TODO']} TODO")

        except Exception as e:
            Logger.error(f"Failed to load existing test results from {execution_key}: {str(e)}")
            Logger.error(f"Response content: {getattr(e, 'response', {}).text if hasattr(e, 'response') else 'No response'}")
            # Fallback: Initialize all as TODO
            for test_id in test_ids:
                cls._test_results_cache[test_id] = "TODO"