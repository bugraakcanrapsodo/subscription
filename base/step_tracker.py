from typing import List, Tuple, Optional, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from base.logger import Logger
import json
import csv
import os
import ast
import re
from datetime import datetime
from base.xray_api import XrayApi

class StepTracker:
    def __init__(self):
        self.steps: List[Tuple[int, str, bool]] = []  # (step_number, step_description, result)
        self.current_step = 0
        self.sub_steps: Dict[int, List[Tuple[str, bool]]] = {}  # {parent_step: [(description, result)]}
        self.current_parent_step = None

    def start_step(self, description: str) -> int:
        """
        Start a new test step and log it.

        Args:
            description: Description of the step

        Returns:
            Current step number
        """
        self.current_step += 1
        Logger.info(f"Step {self.current_step}: {description}")
        self.steps.append((self.current_step, description, None))
        return self.current_step

    def start_sub_steps(self, parent_step: Optional[int] = None) -> int:
        """
        Start tracking sub-steps for a parent step.

        Args:
            parent_step: Step number of the parent step. If None, uses the most recent step.

        Returns:
            The parent step number being tracked
        """
        parent = parent_step if parent_step is not None else self.current_step
        self.current_parent_step = parent
        if parent not in self.sub_steps:
            self.sub_steps[parent] = []
        return parent

    def add_sub_step(self, description: str, result: bool) -> None:
        """
        Add a sub-step result to the current parent step.

        Args:
            description: Description of the sub-step
            result: Whether the sub-step passed (True) or failed (False)
        """
        if self.current_parent_step is None:
            raise ValueError("No parent step set. Call start_sub_steps first.")

        self.sub_steps[self.current_parent_step].append((description, result))
        if result:
            Logger.info(f"  ✓ Sub-step passed: {description}")
        else:
            Logger.error(f"  ✗ Sub-step failed: {description}")

    def finish_sub_steps(self, pass_message: Optional[str] = None, fail_message: Optional[str] = None) -> bool:
        """
        Evaluate all sub-steps for the current parent step and mark the parent as passed/failed.
        Parent step passes only if ALL sub-steps pass.

        Args:
            pass_message: Custom success message for parent step
            fail_message: Custom failure message for parent step

        Returns:
            True if all sub-steps passed, False otherwise
        """
        if self.current_parent_step is None:
            raise ValueError("No parent step set. Call start_sub_steps first.")

        parent_step = self.current_parent_step
        sub_step_results = self.sub_steps.get(parent_step, [])

        # Check if all sub-steps passed
        all_passed = all(result for _, result in sub_step_results)

        # Get index of parent step in steps list (0-based)
        parent_step_idx = next((i for i, (num, _, _) in enumerate(self.steps)
                             if num == parent_step), None)

        if all_passed:
            # All sub-steps passed, mark parent step as passed
            message = pass_message or f"All {len(sub_step_results)} sub-steps passed"
            self.steps[parent_step_idx] = (parent_step, self.steps[parent_step_idx][1], True)
            Logger.info(f"✓ Success: {message}")
        else:
            # Some sub-steps failed, mark parent step as failed
            failed_steps = [desc for desc, result in sub_step_results if not result]
            message = fail_message or f"{len(failed_steps)} sub-steps failed: {', '.join(failed_steps)}"
            self.steps[parent_step_idx] = (parent_step, self.steps[parent_step_idx][1], False)
            Logger.error(f"✗ Failed: Step {parent_step} - {message}")

        # Reset current parent step
        self.current_parent_step = None
        return all_passed

    def pass_step(self, message: Optional[str] = None) -> None:
        """
        Mark the current step as passed.

        Args:
            message: Optional success message to log
        """
        if message:
            Logger.info(f"✓ Success: {message}")
        self.steps[-1] = (self.current_step, self.steps[-1][1], True)

    def fail_step(self, error_message: str) -> None:
        """
        Mark the current step as failed.

        Args:
            error_message: Error message to log
        """
        Logger.error(f"✗ Failed: Step {self.current_step} - {error_message}")
        self.steps[-1] = (self.current_step, self.steps[-1][1], False)

    def get_failed_steps(self) -> List[Tuple[int, str]]:
        """
        Get list of failed steps with their descriptions.

        Returns:
            List of tuples containing step numbers and descriptions of failed steps
        """
        return [(num, desc) for num, desc, result in self.steps if result is False]

    def all_steps_passed(self) -> bool:
        """
        Check if all steps passed.

        Returns:
            True if all steps passed, False otherwise
        """
        return all(result for _, _, result in self.steps if result is not None)

    def get_current_step(self) -> int:
        """
        Get current step number.

        Returns:
            Current step number
        """
        return self.current_step

    def summarize_results(self) -> None:
        """Print summary of test results."""
        failed_steps = self.get_failed_steps()
        if failed_steps:
            step_details = "\n".join([f"  Step {num}: {desc}" for num, desc in failed_steps])
            Logger.error(f"\n✗ Test Failed! Following steps failed:\n{step_details}")
            assert False, f"Test steps failed: {[num for num, _ in failed_steps]}"
        else:
            Logger.info("\n✓ All test steps passed successfully!")

class StepResult(Enum):
    """Enum for test step results"""
    PASSED = "PASSED"
    FAILED = "FAILED"
    PENDING = "PENDING"
    TODO = "TODO"


@dataclass
class XRayTestInfo:
    """Information about linked XRay test"""
    test_key: str
    description: str = ""


@dataclass
class SubStepInfo:
    """Information about a sub-step"""
    description: str
    result: StepResult
    error_message: Optional[str] = None


@dataclass
class TestStepInfo:
    """Information about a test step"""
    step_number: int
    description: str
    result: StepResult
    error_message: Optional[str] = None
    xray_tests: List[XRayTestInfo] = field(default_factory=list)
    sub_steps: List[SubStepInfo] = field(default_factory=list)


class XRayStepTracker:
    """
    Simple step tracker with XRay test mapping and step numbering visibility
    """
    
    # XRay test ID pattern validation - basic format check
    XRAY_TEST_ID_PATTERN = re.compile(r'^[A-Z]+-\d+$')  # Matches format like "RQA-12345", "TEST-123", etc.

    def __init__(self):
        self.steps: List[TestStepInfo] = []
        self.current_step_number = 0
        self.xray_test_results: Dict[str, StepResult] = {}  # test_key -> result
        self.has_pending_substeps = False
    
    @classmethod
    def _validate_xray_test_id(cls, test_id: str) -> bool:
        """
        Validate XRay test ID format.
        
        Args:
            test_id: Test ID to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not test_id or not test_id.strip():
            return False
            
        return bool(cls.XRAY_TEST_ID_PATTERN.match(test_id.strip()))
    
    @classmethod
    def _log_invalid_xray_id_warning(cls, test_id: str, context: str = "") -> None:
        """
        Log warning for invalid XRay test ID without attempting to fix it.
        
        Args:
            test_id: Invalid test ID
            context: Additional context for the warning
        """
        context_msg = f" {context}" if context else ""
        Logger.warning(f"Invalid XRay test ID format: '{test_id}'. Expected format: 'PREFIX-NUMBER' (e.g., 'RQA-12345', 'TEST-123').{context_msg}")
        
        # Provide specific guidance based on common issues
        if test_id.isdigit():
            Logger.warning(f"  → '{test_id}' appears to be missing a prefix. Should it be 'RQA-{test_id}' or another prefix?")
        elif test_id and test_id[0].islower():
            Logger.warning(f"  → '{test_id}' has lowercase letters. XRay test IDs typically use uppercase.")
        elif '-' not in test_id:
            Logger.warning(f"  → '{test_id}' is missing the '-' separator between prefix and number.")

    def step(self,
             step_number: int,
             description: str,
             xray_tests: Optional[List[str]] = None) -> None:
        """
        Start a new test step with explicit step number for code readability.

        Args:
            step_number: Explicit step number (for code readability)
            description: Description of the step
            xray_tests: List of XRay test keys that this step validates
        """
        # If we have pending substeps, conclude the previous step
        if self.has_pending_substeps:
            self._conclude_previous_step()

        # Validate step number sequence
        if len(self.steps) == 0:
            # First step: allow both 0 and 1 as valid starting numbers
            if step_number not in [0, 1]:
                Logger.warning(f"First step number should be 0 or 1, got {step_number}")
        else:
            # Subsequent steps: follow normal sequence validation
            expected_step = self.current_step_number + 1
            if step_number != expected_step:
                Logger.warning(f"Step number mismatch: expected {expected_step}, got {step_number}")

        self.current_step_number = step_number

        # Parse and validate XRay tests
        xray_test_infos = []
        invalid_test_ids = []
        
        if xray_tests:
            for test_key in xray_tests:
                if not test_key or not test_key.strip():
                    continue
                
                test_key = test_key.strip()
                
                if self._validate_xray_test_id(test_key):
                    xray_test_infos.append(XRayTestInfo(test_key=test_key))
                else:
                    invalid_test_ids.append(test_key)
                    self._log_invalid_xray_id_warning(test_key, "This test ID will be ignored.")

        # Log summary for invalid test IDs if any found
        if invalid_test_ids:
            Logger.warning(f"Step {step_number} contains {len(invalid_test_ids)} invalid XRay test IDs that will be ignored: {invalid_test_ids}")
            Logger.warning("Please fix these test IDs in your test code before running XRay integration.")

        # Create step info
        step_info = TestStepInfo(
            step_number=step_number,
            description=description,
            result=StepResult.PENDING,
            xray_tests=xray_test_infos
        )

        # Log step start with XRay info (only valid test IDs)
        valid_test_ids = [info.test_key for info in xray_test_infos]
        xray_info = f" [XRay: {', '.join(valid_test_ids)}]" if valid_test_ids else ""
        if invalid_test_ids:
            xray_info += f" [IGNORED: {', '.join(invalid_test_ids)}]"
            
        Logger.info(f"Step {step_number}: {description}{xray_info}")

        self.steps.append(step_info)

    def pass_step(self, message: Optional[str] = None) -> None:
        """
        Mark the current step as passed

        Args:
            message: Optional success message
        """
        if not self.steps:
            Logger.error("No step to mark as passed")
            return

        current_step = self.steps[-1]

        # If we have pending substeps, conclude them first
        if self.has_pending_substeps:
            self._conclude_previous_step()

        current_step.result = StepResult.PASSED

        success_msg = message or f"Step {current_step.step_number} completed successfully"
        Logger.info(f"✓ Success: {success_msg}")

        # Update XRay test results
        self._update_xray_test_results(current_step)

    def fail_step(self, error_message: str = "") -> None:
        """
        Mark the current step as failed

        Args:
            error_message: Error message describing the failure
        """
        if not self.steps:
            Logger.error("No step to mark as failed")
            return

        current_step = self.steps[-1]

        # If we have pending substeps, conclude them first
        if self.has_pending_substeps:
            self._conclude_previous_step()

        current_step.result = StepResult.FAILED
        current_step.error_message = error_message

        Logger.error(f"✗ Failed: Step {current_step.step_number} - {error_message}")

        # Update XRay test results
        self._update_xray_test_results(current_step)

    def pass_substep(self, description: str, message: Optional[str] = None, debug_log: bool = False) -> None:
        """
        Add a passed sub-step to the current step

        Args:
            description: Sub-step description
            message: Optional success message
            debug_log: Logger.debug logs used if True
        """
        if not self.steps:
            Logger.error("No current step for sub-step")
            return

        current_step = self.steps[-1]

        sub_step = SubStepInfo(
            description=description,
            result=StepResult.PASSED
        )

        current_step.sub_steps.append(sub_step)
        self.has_pending_substeps = True

        log_msg = message or description
        if debug_log == False:
            Logger.info(f"  ✓ Sub-step passed: {log_msg}")
        else:
            Logger.debug(f"  ✓ Sub-step passed: {log_msg}")


    def fail_substep(self, description: str, error_message: str = "") -> None:
        """
        Add a failed sub-step to the current step

        Args:
            description: Sub-step description
            error_message: Error message describing the failure
        """
        if not self.steps:
            Logger.error("No current step for sub-step")
            return

        current_step = self.steps[-1]

        sub_step = SubStepInfo(
            description=description,
            result=StepResult.FAILED,
            error_message=error_message
        )

        current_step.sub_steps.append(sub_step)
        self.has_pending_substeps = True

        Logger.error(f"  ✗ Sub-step failed: {description} - {error_message}")

    def _conclude_previous_step(self) -> None:
        """
        Conclude the previous step based on its sub-steps
        """
        if not self.steps:
            return

        current_step = self.steps[-1]

        if not current_step.sub_steps:
            return

        # Check if all sub-steps passed
        all_passed = all(sub.result == StepResult.PASSED for sub in current_step.sub_steps)

        if all_passed:
            current_step.result = StepResult.PASSED
            Logger.info(f"✓ Success: All {len(current_step.sub_steps)} sub-steps passed")
        else:
            current_step.result = StepResult.FAILED
            failed_subs = [sub.description for sub in current_step.sub_steps if sub.result == StepResult.FAILED]
            current_step.error_message = f"Sub-steps failed: {', '.join(failed_subs)}"
            Logger.error(f"✗ Failed: Step {current_step.step_number} - {len(failed_subs)} sub-steps failed")

        # Update XRay test results
        self._update_xray_test_results(current_step)

        self.has_pending_substeps = False

    def _update_xray_test_results(self, step_info: TestStepInfo) -> None:
        """
        Update XRay test results based on step results

        Args:
            step_info: Step information
        """
        for xray_test in step_info.xray_tests:
            test_key = xray_test.test_key

            # If step failed, mark XRay test as failed
            if step_info.result == StepResult.FAILED:
                self.xray_test_results[test_key] = StepResult.FAILED
            # If step passed, mark XRay test as passed
            elif step_info.result == StepResult.PASSED:
                self.xray_test_results[test_key] = StepResult.PASSED

    def get_xray_test_results(self) -> Dict[str, str]:
        """
        Get XRay test results in format suitable for XRay API

        Returns:
            Dictionary mapping test keys to status strings
        """
        results = {}
        empty_keys_filtered = 0

        for test_key, result in self.xray_test_results.items():
            # Only include non-empty test keys
            if test_key and test_key.strip():
                if result == StepResult.PASSED:
                    results[test_key] = StepResult.PASSED.value
                elif result == StepResult.FAILED:
                    results[test_key] = StepResult.FAILED.value
                else:
                    results[test_key] = StepResult.TODO.value
            else:
                empty_keys_filtered += 1
                Logger.debug(f"Filtered out empty XRay test key with result: {result}")

        if empty_keys_filtered > 0:
            Logger.info(f"Filtered out {empty_keys_filtered} empty XRay test keys")

        return results

    def get_failed_steps(self) -> List[Tuple[int, str]]:
        """
        Get list of failed steps

        Returns:
            List of (step_number, description) tuples
        """
        return [(step.step_number, step.description) for step in self.steps if step.result == StepResult.FAILED]

    def all_steps_passed(self) -> bool:
        """
        Check if all steps passed

        Returns:
            True if all steps passed
        """
        return all(step.result == StepResult.PASSED for step in self.steps)

    def summarize_results(self) -> None:
        """Print test results summary and assert if failed"""
        # Conclude any pending substeps
        if self.has_pending_substeps:
            self._conclude_previous_step()

        failed_steps = self.get_failed_steps()

        # Print step summary
        if failed_steps:
            step_details = "\n".join([f"  Step {num}: {desc}" for num, desc in failed_steps])
            Logger.error(f"\n✗ Test Failed! Following steps failed:\n{step_details}")
        else:
            Logger.info("\n✓ All test steps passed successfully!")

        # Print XRay test summary if any
        if self.xray_test_results:
            Logger.info("\n📊 XRay Test Results:")
            for test_key, result in self.xray_test_results.items():
                status_icon = "✓" if result == StepResult.PASSED else "✗"
                Logger.info(f"  {status_icon} {test_key}: {result.value}")

        # Assert failure if any steps failed
        if failed_steps:
            assert False, f"Test steps failed: {[num for num, _ in failed_steps]}"

    def update_xray_test_titles(self, xray_titles: Dict[str, str]) -> None:
        """
        Update XRay test titles after fetching from XRay API

        Args:
            xray_titles: Dictionary mapping test_key -> title
        """
        for step in self.steps:
            for xray_test in step.xray_tests:
                if xray_test.test_key in xray_titles:
                    xray_test.description = xray_titles[xray_test.test_key]

        Logger.info(f"Updated {len(xray_titles)} XRay test titles")

    def export_step_mapping_csv(self, filename: str = "test_step_xray_mapping.csv") -> str:
        """
        Export step-to-XRay mapping to CSV file for documentation

        Args:
            filename: Output CSV filename

        Returns:
            Path to the created CSV file
        """
        # Conclude any pending substeps
        if self.has_pending_substeps:
            self._conclude_previous_step()

        # Prepare data for CSV
        csv_data = []

        for step in self.steps:
            if step.xray_tests:
                # If step has XRay tests, create a row for each XRay test
                for xray_test in step.xray_tests:
                    csv_data.append({
                        'Test_No': 1,
                        'Step_No': step.step_number,
                        'Test_Step_Description': step.description,
                        'XRay_ID': xray_test.test_key,
                        'XRay_Title': xray_test.description or 'Title to be fetched from XRay API',
                        'Step_Result': step.result.value,
                        'Error_Message': step.error_message or '',
                        'XRay_Test_Result': self.xray_test_results.get(xray_test.test_key, StepResult.PENDING).value
                    })
            else:
                # If step has no XRay tests, still include it
                csv_data.append({
                    'Test_No': 1,
                    'Step_No': step.step_number,
                    'Test_Step_Description': step.description,
                    'XRay_ID': '',
                    'XRay_Title': '',
                    'Step_Result': step.result.value,
                    'Error_Message': step.error_message or '',
                    'XRay_Test_Result': ''
                })

        # Write to CSV
        if csv_data:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Test_No', 'Step_No', 'Test_Step_Description', 'XRay_ID', 'XRay_Title', 'Step_Result', 'Error_Message', 'XRay_Test_Result']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerows(csv_data)

        full_path = os.path.abspath(filename)
        Logger.info(f"Step-to-XRay mapping exported to: {full_path}")
        return full_path

    def export_step_mapping_excel(self, filename: str = "test_step_xray_mapping.xlsx") -> str:
        """
        Export step-to-XRay mapping to Excel file for documentation

        Args:
            filename: Output Excel filename

        Returns:
            Path to the created Excel file
        """
        try:
            import pandas as pd

            # Conclude any pending substeps
            if self.has_pending_substeps:
                self._conclude_previous_step()

            # Prepare data for Excel
            excel_data = []

            for step in self.steps:
                if step.xray_tests:
                    for xray_test in step.xray_tests:
                        excel_data.append({
                            'Test No': 1,
                            'Step No': step.step_number,
                            'Test Step Description': step.description,
                            'XRay ID': xray_test.test_key,
                            'XRay Title': xray_test.description or 'Title to be fetched from XRay API',
                            'Step Result': step.result.value,
                            'Error Message': step.error_message or '',
                            'XRay Test Result': self.xray_test_results.get(xray_test.test_key, StepResult.PENDING).value
                        })
                else:
                    excel_data.append({
                        'Test No': 1,
                        'Step No': step.step_number,
                        'Test Step Description': step.description,
                        'XRay ID': '',
                        'XRay Title': '',
                        'Step Result': step.result.value,
                        'Error Message': step.error_message or '',
                        'XRay Test Result': ''
                    })

            # Create DataFrame and export to Excel
            if excel_data:
                df = pd.DataFrame(excel_data)
                df.to_excel(filename, sheet_name='Test Step Mapping', index=False)

            full_path = os.path.abspath(filename)
            Logger.info(f"Step-to-XRay mapping exported to Excel: {full_path}")
            return full_path

        except ImportError:
            Logger.error("pandas is required for Excel export. Install with: pip install pandas openpyxl")
            return self.export_step_mapping_csv(filename.replace('.xlsx', '.csv'))
        except Exception as e:
            Logger.error(f"Failed to export Excel file: {str(e)}")
            return self.export_step_mapping_csv(filename.replace('.xlsx', '.csv'))


class XRayTestCollector:
    """
    Utility class to collect all XRay test IDs from step_tracker.step() calls
    across all test files using AST parsing.
    """

    def __init__(self, test_directory: str = "pro20Runner/e2e_tests"):
        self.test_directory = test_directory
        self.collected_tests: Dict[str, List[str]] = {}  # file_name -> list of test IDs
        self.all_test_ids: Set[str] = set()

    def collect_all_xray_tests(self) -> List[str]:
        """
        Collect all XRay test IDs from step_tracker.step() calls in test files.

        Returns:
            List of unique XRay test IDs
        """
        Logger.info(f"Collecting XRay test IDs from directory: {self.test_directory}")

        # Get all Python test files
        test_files = self._get_test_files()

        # Parse each file
        for file_path in test_files:
            try:
                test_ids = self._parse_file_for_xray_tests(file_path)
                if test_ids:
                    file_name = os.path.basename(file_path)
                    self.collected_tests[file_name] = test_ids
                    self.all_test_ids.update(test_ids)
                    unique_test_ids = list(set(test_ids))
                    Logger.info(f"Found {len(test_ids)} XRay tests ({len(unique_test_ids)} unique) in {file_name}: {unique_test_ids}")
            except Exception as e:
                Logger.error(f"Failed to parse {file_path}: {str(e)}")

        all_tests = list(self.all_test_ids)
        Logger.info(f"Total unique XRay tests: {len(all_tests)}")
        return all_tests

    def collect_xray_tests_from_pytest_items(self, pytest_items) -> List[str]:
        """
        Collect XRay test IDs from pytest collected items only.
        This ensures we only collect tests that will actually run.

        Args:
            pytest_items: List of pytest collected test items

        Returns:
            List of unique XRay test IDs from collected tests only
        """
        # Filter out skipped tests - only collect from tests that will actually run
        non_skipped_items = [
            item for item in pytest_items 
            if not any(marker.name == 'skip' for marker in item.own_markers)
        ]
        
        Logger.info(f"Collecting XRay test IDs from {len(non_skipped_items)} pytest items (filtered from {len(pytest_items)} total)")

        collected_test_ids = set()
        processed_files = set()

        for item in non_skipped_items:
            try:
                # Get the file path for this test item
                test_file_path = str(item.fspath) if hasattr(item, 'fspath') else str(item.path)
                file_name = os.path.basename(test_file_path)

                # Skip if we've already processed this file (optimization)
                if test_file_path in processed_files:
                    continue

                # Parse the test file for XRay test IDs
                test_ids = self._parse_file_for_xray_tests(test_file_path)

                if test_ids:
                    # Filter test IDs: only keep those from functions that are in collected items
                    relevant_test_ids = self._filter_test_ids_for_collected_items(
                        test_file_path, test_ids, pytest_items
                    )

                    if relevant_test_ids:
                        collected_test_ids.update(relevant_test_ids)
                        self.collected_tests[file_name] = relevant_test_ids
                        Logger.debug(f"Found {len(relevant_test_ids)} relevant XRay tests in {file_name}: {relevant_test_ids}")

                processed_files.add(test_file_path)

            except Exception as e:
                Logger.error(f"Failed to process pytest item {item}: {str(e)}")

        all_tests = list(collected_test_ids)
        self.all_test_ids.update(collected_test_ids)
        Logger.info(f"Total unique XRay tests from collected items: {len(all_tests)}")
        return all_tests

    def _filter_test_ids_for_collected_items(self, file_path: str, test_ids: List[str], pytest_items) -> List[str]:
        """
        Filter XRay test IDs to only include those from test functions that are in pytest collected items.

        Args:
            file_path: Path to the test file
            test_ids: All XRay test IDs found in the file
            pytest_items: Pytest collected items (should already be filtered to non-skipped items)

        Returns:
            List of XRay test IDs that belong to collected test functions
        """
        # Get the set of test function names that are collected for this file
        # Only include non-skipped tests
        collected_function_names = set()
        for item in pytest_items:
            # Skip if test is marked to be skipped
            if any(marker.name == 'skip' for marker in item.own_markers):
                continue
                
            item_file_path = str(item.fspath) if hasattr(item, 'fspath') else str(item.path)
            if item_file_path == file_path:
                # Extract function name from the item
                function_name = item.name.split('[')[0]  # Remove parametrization part if present
                collected_function_names.add(function_name)

        if not collected_function_names:
            return []

        # Parse the file to map XRay test IDs to their containing functions
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            # Find all test functions and their XRay test IDs
            relevant_test_ids = []

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name in collected_function_names:
                    # This function is in collected items, find XRay test IDs within it
                    function_xray_ids = self._extract_xray_tests_from_function(node)
                    relevant_test_ids.extend(function_xray_ids)

            return relevant_test_ids

        except Exception as e:
            Logger.warning(f"Failed to filter test IDs for {file_path}: {str(e)}, returning all test IDs")
            return test_ids  # Fallback: return all test IDs if filtering fails

    def _extract_xray_tests_from_function(self, function_node: ast.FunctionDef) -> List[str]:
        """
        Extract XRay test IDs from a specific function node.

        Args:
            function_node: AST function definition node

        Returns:
            List of XRay test IDs found in this function
        """
        xray_tests = []

        # Walk through all nodes in this function
        for node in ast.walk(function_node):
            if isinstance(node, ast.Call) and self._is_step_tracker_call(node):
                # Extract xray_tests parameter
                test_ids = self._extract_xray_tests_from_call(node)
                xray_tests.extend(test_ids)

        return xray_tests

    def _get_test_files(self) -> List[str]:
        """Get all Python test files from the test directory."""
        test_files = []

        if not os.path.exists(self.test_directory):
            Logger.error(f"Test directory not found: {self.test_directory}")
            return test_files

        for file_name in os.listdir(self.test_directory):
            if file_name.startswith("test_") and file_name.endswith(".py"):
                file_path = os.path.join(self.test_directory, file_name)
                test_files.append(file_path)

        Logger.debug(f"Found {len(test_files)} test files")
        return test_files

    def _parse_file_for_xray_tests(self, file_path: str) -> List[str]:
        """
        Parse a single Python file to extract XRay test IDs from step_tracker.step() calls.

        Args:
            file_path: Path to the Python file

        Returns:
            List of XRay test IDs found in the file
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the file into an AST
        tree = ast.parse(content)

        # Find all step_tracker.step() calls
        xray_tests = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Check if this is a step_tracker.step() call
                if self._is_step_tracker_call(node):
                    # Extract xray_tests parameter
                    test_ids = self._extract_xray_tests_from_call(node)
                    xray_tests.extend(test_ids)

        return xray_tests

    def _is_step_tracker_call(self, call_node: ast.Call) -> bool:
        """Check if the call node is a step_tracker.step() call."""
        if isinstance(call_node.func, ast.Attribute):
            # Handle step_tracker.step() calls
            if (isinstance(call_node.func.value, ast.Name) and
                call_node.func.value.id == "step_tracker" and
                call_node.func.attr == "step"):
                return True
        return False

    def _extract_xray_tests_from_call(self, call_node: ast.Call) -> List[str]:
        """Extract XRay test IDs from the xray_tests parameter of a step() call."""
        xray_tests = []

        # Look for xray_tests parameter in keyword arguments
        for keyword in call_node.keywords:
            if keyword.arg == "xray_tests":
                # Extract the list of test IDs
                if isinstance(keyword.value, ast.List):
                    for element in keyword.value.elts:
                        test_id = None
                        if isinstance(element, ast.Constant) and isinstance(element.value, str):
                            test_id = element.value
                        elif isinstance(element, ast.Str):  # For Python < 3.8 compatibility
                            test_id = element.s

                        # Validate test IDs (no auto-correction)
                        if test_id and test_id.strip():
                            test_id = test_id.strip()
                            if XRayStepTracker._validate_xray_test_id(test_id):
                                xray_tests.append(test_id)
                            else:
                                XRayStepTracker._log_invalid_xray_id_warning(test_id, "Skipping during collection.")

        return xray_tests

    def get_test_mapping(self) -> Dict[str, List[str]]:
        """
        Get mapping of test files to their XRay test IDs.

        Returns:
            Dictionary mapping file names to lists of XRay test IDs
        """
        return self.collected_tests.copy()
