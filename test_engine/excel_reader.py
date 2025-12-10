"""
Excel Reader
Parses test cases from Excel/CSV files
"""

import pandas as pd
from typing import List, Dict, Any
from pathlib import Path
from base.logger import Logger


class ExcelReader:
    """
    Read and parse test cases from Excel or CSV files
    """
    
    def __init__(self, file_path: str):
        """
        Initialize Excel reader
        
        Args:
            file_path: Path to Excel (.xlsx) or CSV (.csv) file
        """
        self.file_path = Path(file_path)
        self.logger = Logger(__name__)
        
        if not self.file_path.exists():
            raise FileNotFoundError(f"Test file not found: {file_path}")
        
        # Validate file extension
        if self.file_path.suffix not in ['.xlsx', '.xls', '.csv']:
            raise ValueError(f"Unsupported file format: {self.file_path.suffix}. Use .xlsx, .xls, or .csv")
    
    def read_test_cases(self) -> List[Dict[str, Any]]:
        """
        Read all test cases from file
        
        Returns:
            List of test case dictionaries
        """
        self.logger.info(f"Reading test cases from: {self.file_path}")
        
        # Read file based on extension
        if self.file_path.suffix == '.csv':
            df = pd.read_csv(self.file_path)
        else:
            df = pd.read_excel(self.file_path)
        
        # Convert to list of dictionaries
        test_cases = df.to_dict('records')
        
        # Clean up NaN values
        test_cases = self._clean_test_cases(test_cases)
        
        self.logger.info(f"Loaded {len(test_cases)} test case(s)")
        
        return test_cases
    
    def _clean_test_cases(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean test cases by:
        - Removing NaN values
        - Converting to appropriate types
        - Validating required fields
        
        Args:
            test_cases: Raw test cases from pandas
            
        Returns:
            Cleaned test cases
        """
        cleaned = []
        
        for idx, test_case in enumerate(test_cases, start=1):
            # Replace NaN with None or empty string
            clean_case = {}
            for key, value in test_case.items():
                if pd.isna(value):
                    clean_case[key] = None
                else:
                    clean_case[key] = value
            
            # Validate required fields
            if not clean_case.get('test_id'):
                self.logger.warning(f"Row {idx}: Missing test_id, skipping")
                continue
            
            # Check if at least action_1 is provided
            #if not clean_case.get('action_1'):
            #    self.logger.warning(f"Test {clean_case['test_id']}: No actions defined, skipping")
            #    continue
            
            # Set default trial_status if not provided or NaN
            # Note: "None" in Excel becomes NaN when read by pandas
            if 'trial_status' not in clean_case or clean_case.get('trial_status') is None or pd.isna(clean_case.get('trial_status')):
                clean_case['trial_status'] = 'None'  # Default to trial NOT eligible for empty cells
            
            cleaned.append(clean_case)
        
        return cleaned
    
    def get_test_case_by_id(self, test_id: str) -> Dict[str, Any]:
        """
        Get a specific test case by ID
        
        Args:
            test_id: Test case identifier
            
        Returns:
            Test case dictionary or None if not found
        """
        test_cases = self.read_test_cases()
        
        for test_case in test_cases:
            if str(test_case.get('test_id')) == str(test_id):
                return test_case
        
        raise ValueError(f"Test case not found: {test_id}")
    
    def parse_actions(self, test_case: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Parse actions from a test case
        
        Args:
            test_case: Test case dictionary
            
        Returns:
            List of action dictionaries with 'action' and 'param' keys
        """
        actions = []
        
        # Support up to 10 actions (action_1 through action_10)
        for i in range(1, 11):
            action_key = f'action_{i}'
            param_key = f'param_{i}'
            
            action_name = test_case.get(action_key)
            
            # Stop if no more actions
            if not action_name:
                break
            
            actions.append({
                'action': action_name,
                'param': test_case.get(param_key)
            })
        
        return actions

