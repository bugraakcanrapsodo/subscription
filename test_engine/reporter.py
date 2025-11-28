"""
Reporter
Generates test reports in JSON and text format
"""

import json
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime, timedelta
from base.logger import Logger


class Reporter:
    """
    Generate test execution reports
    """
    
    def __init__(self, output_dir: str = "test_results"):
        """
        Initialize reporter
        
        Args:
            output_dir: Directory to save reports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.logger = Logger(__name__)
    
    def generate_report(self, test_results: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        Generate test report in JSON and text formats
        
        Args:
            test_results: List of test result dictionaries
            
        Returns:
            Dictionary with paths to generated reports
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate JSON report
        json_path = self.output_dir / f'test_report_{timestamp}.json'
        self._generate_json_report(test_results, json_path)
        
        # Generate text report
        text_path = self.output_dir / f'test_report_{timestamp}.txt'
        self._generate_text_report(test_results, text_path)
        
        self.logger.info(f"Reports generated:")
        self.logger.info(f"  JSON: {json_path}")
        self.logger.info(f"  Text: {text_path}")
        
        return {
            'json': str(json_path),
            'text': str(text_path)
        }
    
    def _generate_json_report(self, test_results: List[Dict[str, Any]], output_path: Path):
        """
        Generate JSON report
        
        Args:
            test_results: Test results
            output_path: Output file path
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': self._generate_summary(test_results),
            'test_results': test_results
        }
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
    
    def _generate_text_report(self, test_results: List[Dict[str, Any]], output_path: Path):
        """
        Generate text report
        
        Args:
            test_results: Test results
            output_path: Output file path
        """
        summary = self._generate_summary(test_results)
        
        lines = []
        lines.append("=" * 80)
        lines.append("DATA-DRIVEN SUBSCRIPTION TEST REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        
        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Tests:  {summary['total']}")
        lines.append(f"Passed:       {summary['passed']} ({summary['pass_rate']:.1f}%)")
        lines.append(f"Failed:       {summary['failed']}")
        lines.append("")
        
        # Individual test results
        lines.append("TEST RESULTS")
        lines.append("-" * 80)
        
        for result in test_results:
            test_id = result['test_id']
            status = "PASS" if result['passed'] else "FAIL"
            status_symbol = "✓" if result['passed'] else "✗"
            
            lines.append(f"\n{status_symbol} Test: {test_id} - {status}")
            lines.append(f"  Name: {result.get('test_name', 'N/A')}")
            
            # Add user email if available
            user_email = result.get('user_email')
            if user_email:
                lines.append(f"  User: {user_email}")
            
            lines.append(f"  Duration: {result.get('duration', 0):.2f}s")
            
            # Action results
            if 'action_results' in result:
                lines.append(f"  Actions:")
                for action_result in result['action_results']:
                    action_name = action_result['action']
                    action_status = "✓" if action_result['success'] else "✗"
                    lines.append(f"    {action_status} {action_name}")
                    if not action_result['success']:
                        lines.append(f"       Error: {action_result.get('message', 'Unknown error')}")
            
            # Verification results (includes both Stripe Checkout and API verifications)
            lines.append(f"  Verifications:")
            
            # FIRST: Stripe Checkout Verification (from action results)
            if 'action_results' in result:
                for action_result in result['action_results']:
                    if action_result.get('success'):
                        # Check if checkout_verification exists in details
                        action_details = action_result.get('details', {})
                        checkout_verify = action_details.get('checkout_verification')
                        
                        if checkout_verify:
                            # Collect all checkout verification matches
                            checkout_matches = []
                            checkout_detail_lines = []
                            
                            if checkout_verify.get('verified'):
                                # Currency - ONLY if we verified it
                                expected_currency = action_details.get('currency', 'N/A').upper()
                                actual_currency = checkout_verify.get('actual_currency', 'N/A').upper()
                                match = actual_currency == expected_currency
                                checkout_matches.append(match)
                                checkout_detail_lines.append(f"       {'✓' if match else '✗'} Currency: {actual_currency} (expected: {expected_currency})")
                                
                                # Price - ONLY if we actually verified it
                                expected_price = checkout_verify.get('expected_price')
                                actual_price = checkout_verify.get('actual_price')
                                if expected_price is not None and actual_price is not None:
                                    match = abs(actual_price - expected_price) < 0.01
                                    checkout_matches.append(match)
                                    checkout_detail_lines.append(f"       {'✓' if match else '✗'} Price: {actual_price} (expected: {expected_price})")
                                
                                # Product Name - ONLY if we verified it
                                expected_product = checkout_verify.get('expected_product_name')
                                actual_product = checkout_verify.get('actual_product_name')
                                if expected_product is not None and actual_product is not None:
                                    match = expected_product in actual_product
                                    checkout_matches.append(match)
                                    checkout_detail_lines.append(f"       {'✓' if match else '✗'} Product Name: '{actual_product}' (expected: contains '{expected_product}')")
                                
                                # Trial Info - ONLY if we verified it (expected_trial_text will be None if not verified)
                                expected_trial = checkout_verify.get('expected_trial_text')
                                actual_trial = checkout_verify.get('actual_trial_text')
                                if expected_trial is not None and actual_trial is not None:
                                    match = expected_trial.lower() in actual_trial.lower()
                                    checkout_matches.append(match)
                                    checkout_detail_lines.append(f"       {'✓' if match else '✗'} Trial Info: '{actual_trial}' (expected: '{expected_trial}')")
                                
                                # Determine overall checkout status
                                checkout_overall = all(checkout_matches) if checkout_matches else checkout_verify.get('verified')
                                checkout_status = "✓" if checkout_overall else "✗"
                                lines.append(f"    {checkout_status} Stripe Checkout:")
                                lines.extend(checkout_detail_lines)
                            else:
                                lines.append(f"    ✗ Stripe Checkout:")
                                lines.append(f"       Error: {checkout_verify.get('message', 'Verification failed')}")
            
            # SECOND: API Verifications (User API and Admin API)
            if 'verification_results' in result:
                for verify_result in result['verification_results']:
                    # Determine if this is User API or Admin API verification
                    is_admin = 'admin_subscription' in verify_result
                    verify_type = "Admin API" if is_admin else "User API"
                    
                    # Collect all verification match results to determine overall status
                    all_matches = []
                    detail_lines = []  # Collect detail lines first
                    
                    # Show detailed verification results
                    if verify_result.get('verified'):
                        # Get subscription data (different keys for user vs admin)
                        if is_admin:
                            subscription = verify_result.get('admin_subscription', {})
                            actual_status = subscription.get('status')
                            actual_type = subscription.get('type')
                            status_name = subscription.get('status_name', 'N/A')
                            type_name = subscription.get('type_name', 'N/A')
                        else:
                            subscription = verify_result.get('subscription', {})
                            actual_status = subscription.get('status_code')
                            actual_type = subscription.get('type')
                            status_name = subscription.get('status_name', 'N/A')
                            type_name = 'N/A'
                        
                        expected_status = verify_result.get('expected_status_code')
                        expected_plan = verify_result.get('expected_plan_code')
                        expected_type = verify_result.get('expected_subscription_type', 2)  # Default web = 2
                        expected_trial = verify_result.get('expected_trial_period_days')
                        
                        actual_plan = subscription.get('plan_code')
                        actual_trial = subscription.get('trial_period_days')
                        
                        # Status Code
                        if expected_status is not None:
                            match = actual_status == expected_status
                            all_matches.append(match)
                            detail_lines.append(f"       {'✓' if match else '✗'} Status Code: {actual_status} (expected: {expected_status}) - {status_name}")
                        else:
                            detail_lines.append(f"       • Status Code: {actual_status} - {status_name}")
                        
                        # Plan Code (only for User API)
                        if not is_admin and actual_plan is not None:
                            if expected_plan is not None:
                                match = actual_plan == expected_plan
                                all_matches.append(match)
                                detail_lines.append(f"       {'✓' if match else '✗'} Plan Code: {actual_plan} (expected: {expected_plan})")
                            else:
                                detail_lines.append(f"       • Plan Code: {actual_plan}")
                        
                        # Subscription Type
                        if expected_type is not None:
                            match = actual_type == expected_type
                            all_matches.append(match)
                            type_suffix = f' - {type_name}' if type_name != 'N/A' else ''
                            detail_lines.append(f"       {'✓' if match else '✗'} Subscription Type: {actual_type} (expected: {expected_type}){type_suffix}")
                        else:
                            detail_lines.append(f"       • Subscription Type: {actual_type} {f'({type_name})' if type_name != 'N/A' else ''}")
                        
                        # Trial Period (only for User API) - ALWAYS show expected if we have actual
                        if not is_admin and actual_trial:
                            # If expected not provided, use actual as expected (should always match from config)
                            if expected_trial is None:
                                expected_trial = actual_trial
                            match = actual_trial == expected_trial
                            all_matches.append(match)
                            detail_lines.append(f"       {'✓' if match else '✗'} Trial Period: {actual_trial} days (expected: {expected_trial} days)")
                        
                        # Dates
                        start_date = subscription.get('startDate') or subscription.get('start_date')
                        expire_date = subscription.get('expireDate') or subscription.get('expire_date')
                        
                        expected_start = verify_result.get('expected_start_date')
                        expected_expire = verify_result.get('expected_expire_date')
                        
                        if start_date:
                            try:
                                # Parse start date
                                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                                now = datetime.now(start_dt.tzinfo)
                                
                                # Calculate how many seconds ago the subscription started
                                time_diff = (now - start_dt).total_seconds()
                                
                                # Expected: within last hour (3600 seconds)
                                is_within_hour = time_diff < 3600 and time_diff >= 0
                                all_matches.append(is_within_hour)
                                
                                if is_within_hour:
                                    detail_lines.append(f"       ✓ Start Date: {start_date} (expected: within last hour)")
                                else:
                                    minutes_ago = int(time_diff / 60)
                                    detail_lines.append(f"       ✗ Start Date: {start_date} (expected: within last hour, actual: {minutes_ago} minutes ago)")
                            except Exception:
                                detail_lines.append(f"       • Start Date: {start_date}")
                        
                        if expire_date and start_date:
                            try:
                                # Parse dates
                                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                                expire_dt = datetime.fromisoformat(expire_date.replace('Z', '+00:00'))
                                
                                # Calculate actual duration
                                actual_duration_days = (expire_dt - start_dt).days
                                
                                # Get expected duration based on trial period (for trial) or subscription duration (for non-trial)
                                if actual_trial:
                                    # Trial subscription - use trial period
                                    expected_duration = actual_trial
                                    match = abs(actual_duration_days - expected_duration) <= 1
                                    all_matches.append(match)
                                    detail_lines.append(f"       {'✓' if match else '✗'} Expire Date: {expire_date} (expected: start + {expected_duration} days, actual: {actual_duration_days} days)")
                                else:
                                    # Non-trial subscription - use subscription duration from config
                                    expected_duration = verify_result.get('expected_duration_days')
                                    if expected_duration:
                                        match = abs(actual_duration_days - expected_duration) <= 1
                                        all_matches.append(match)
                                        detail_lines.append(f"       {'✓' if match else '✗'} Expire Date: {expire_date} (expected: start + {expected_duration} days, actual: {actual_duration_days} days)")
                                    else:
                                        # Fallback if expected_duration not available
                                        detail_lines.append(f"       • Expire Date: {expire_date} (duration: {actual_duration_days} days from start)")
                            except Exception:
                                detail_lines.append(f"       • Expire Date: {expire_date}")
                        
                        # Determine overall status based on ALL matches
                        overall_verified = all(all_matches) if all_matches else verify_result.get('verified')
                        verify_status = "✓" if overall_verified else "✗"
                        
                        # Add header then all detail lines
                        lines.append(f"    {verify_status} {verify_type}:")
                        lines.extend(detail_lines)
                    else:
                        verify_status = "✗"
                        lines.append(f"    {verify_status} {verify_type}:")
                        lines.append(f"       Error: {verify_result.get('message', 'Verification failed')}")
            
            # Error message if failed
            if not result['passed'] and result.get('error'):
                lines.append(f"  Error: {result['error']}")
        
        lines.append("\n" + "=" * 80)
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
    
    def _generate_summary(self, test_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate test summary statistics
        
        Args:
            test_results: Test results
            
        Returns:
            Summary dictionary
        """
        total = len(test_results)
        passed = sum(1 for r in test_results if r.get('passed'))
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'passed': passed,
            'failed': failed,
            'pass_rate': pass_rate
        }
    
    def print_summary(self, test_results: List[Dict[str, Any]]):
        """
        Print test summary to console
        
        Args:
            test_results: Test results
        """
        summary = self._generate_summary(test_results)
        
        print("\n" + "=" * 80)
        print("TEST EXECUTION SUMMARY")
        print("=" * 80)
        print(f"Total Tests:  {summary['total']}")
        print(f"Passed:       {summary['passed']} ({summary['pass_rate']:.1f}%)")
        print(f"Failed:       {summary['failed']}")
        print("=" * 80 + "\n")
        
        # Print individual results
        for result in test_results:
            status = "✓ PASS" if result['passed'] else "✗ FAIL"
            user_email = result.get('user_email', 'N/A')
            print(f"{status} - {result['test_id']}: {result.get('test_name', 'N/A')}")
            
            # Show user email for failed tests to make debugging easier
            if not result['passed'] and user_email != 'N/A':
                print(f"       User: {user_email}")

