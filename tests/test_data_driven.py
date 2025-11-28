"""
Data-Driven Test Suite
Pytest entry point for Excel/CSV-based subscription tests

Note: All fixtures and pytest configuration are in conftest.py and fixtures.py
"""

import pytest
import os


def test_data_driven_execution(test_config, test_executor):
    """
    Main test function that executes data-driven tests from Excel/CSV
    
    Usage:
        # Run all tests from Excel file
        pytest tests/test_data_driven.py --excel examples/mvp_test_cases.xlsx -v -s
        
        # Run specific test
        pytest tests/test_data_driven.py --excel examples/mvp_test_cases.xlsx --test-id MVP001 -v -s
        
        # Run with cleanup
        pytest tests/test_data_driven.py --excel examples/mvp_test_cases.xlsx --cleanup-users -v -s
    """
    # Check if Excel file is provided
    if not test_config['excel_file']:
        pytest.skip("No Excel file provided. Use --excel option")
    
    # Verify file exists
    excel_path = test_config['excel_file']
    if not os.path.exists(excel_path):
        pytest.fail(f"Excel file not found: {excel_path}")
    
    # Run tests
    test_results = test_executor.run_tests_from_file(
        file_path=excel_path,
        test_id=test_config['test_id']
    )
    
    # Check if any test failed
    failed_tests = [r for r in test_results if not r['passed']]
    
    if failed_tests:
        failed_ids = [r['test_id'] for r in failed_tests]
        pytest.fail(f"{len(failed_tests)} test(s) failed: {', '.join(failed_ids)}")


if __name__ == "__main__":
    """
    Allow running directly without pytest command
    
    Usage:
        python tests/test_data_driven.py --excel examples/mvp_test_cases.xlsx
    """
    import sys
    from api.mlm_api import MlmAPI
    from test_engine.executor import TestExecutor
    
    # Simple argument parsing for direct execution
    if "--excel" in sys.argv:
        excel_idx = sys.argv.index("--excel")
        if excel_idx + 1 < len(sys.argv):
            excel_file = sys.argv[excel_idx + 1]
            
            # Create API and executor
            api = MlmAPI(env='test')
            executor = TestExecutor(api)
            
            # Run tests
            executor.run_tests_from_file(excel_file)
        else:
            print("Error: --excel requires a file path")
            sys.exit(1)
    else:
        print("Usage: python test_data_driven.py --excel <path_to_excel>")
        print("   Or: pytest tests/test_data_driven.py --excel <path_to_excel> -v -s")
        sys.exit(1)


