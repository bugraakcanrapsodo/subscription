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
        
        # Concise test list
        lines.append("TEST LIST")
        lines.append("-" * 80)
        for result in test_results:
            status_symbol = "✓" if result['passed'] else "✗"
            status_text = "PASS" if result['passed'] else "FAIL"
            test_id = result['test_id']
            test_name = result.get('test_name', 'N/A')
            lines.append(f"{status_symbol} {test_id} - {status_text} - {test_name}")
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
            
            # Action results - just list what actions were executed (no verification status)
            if 'action_results' in result:
                lines.append(f"  Actions Executed:")
                for idx, action_result in enumerate(result['action_results'], 1):
                    action_name = action_result['action']
                    param = action_result.get('param')

                    # Format with parameter if present
                    if param:
                        action_display = f"{action_name} ({param})"
                    else:
                        action_display = action_name

                    if action_result['success']:
                        lines.append(f"    {idx}. {action_display}")
                    else:
                        failure_msg = action_result.get('message', 'Unknown error')
                        lines.append(f"    {idx}. {action_display} [FAILED]")
                        lines.append(f"        Error: {failure_msg}")

            # Verification results - grouped by action
            lines.append(f"  Verifications:")
            
            # Group all verifications by action name
            action_verifications = {}  # {action_name: {stripe_checkout, user_api, admin_api, manual}}
            
            # Collect all verifications from verification_results
            if 'verification_results' in result:
                for verify_result in result['verification_results']:
                    action_name = verify_result.get('action_name', 'unknown')
                    if action_name not in action_verifications:
                        action_verifications[action_name] = {}
                    
                    verification_type = verify_result.get('verification_type', 'unknown')
                    if verification_type == 'stripe_checkout':
                        action_verifications[action_name]['stripe_checkout'] = verify_result
                    elif verification_type == 'user_api':
                        action_verifications[action_name]['user_api'] = verify_result
                    elif verification_type == 'admin_api':
                        action_verifications[action_name]['admin_api'] = verify_result
                    elif verification_type == 'manual':
                        action_verifications[action_name]['manual'] = verify_result

            
            # Now output verifications grouped by action
            for action_name, verifications in action_verifications.items():
                lines.append(f"\n    Action: {action_name}")
                
                if 'manual' in verifications:
                    verify_result = verifications['manual']
                    manual = verify_result.get('manual_verification', {})
                    passed = manual.get('passed', False)
                    result_text = manual.get('result', 'unknown')
                    hint = manual.get('hint', '')
                    notes = manual.get('notes', '')
                    timestamp = manual.get('timestamp', '')

                    lines.append(f"      {'✓' if passed else '✗'} Manual Verification: {result_text.upper()}")
                    lines.append(f"         Hint: {hint}")
                    lines.append(f"         Timestamp: {timestamp}")

                    if notes:
                        lines.append(f"         Notes:")
                        for note_line in notes.split('\n'):
                            lines.append(f"           {note_line}")

                    # Manual verification actions don't have checkout/user/admin API verifications
                    # So continue to next action
                    continue


                # 1. Stripe Checkout Verification (for purchase actions)
                if 'stripe_checkout' in verifications:
                    verify_result = verifications['stripe_checkout']
                    checks = verify_result.get('checks', {})
                    overall_verified = verify_result.get('verified')
                    
                    detail_lines = []
                    
                    # Display each check that was performed
                    check_order = ['currency', 'currency_consistency', 'subtotal_amount', 'total_amount', 'subtotal_total_match', 'product_name', 'trial_info', 'trial_amount']
                    
                    for check_name in check_order:
                        if check_name not in checks:
                            continue
                            
                        check = checks[check_name]
                        passed = check.get('passed')
                        expected = check.get('expected')
                        actual = check.get('actual')
                        message = check.get('message', '')
                        
                        icon = '✓' if passed else '✗'
                        
                        # Format based on check type
                        if check_name == 'currency':
                            detail_lines.append(f"         {icon} Currency: {actual} (expected: {expected})")
                        elif check_name == 'currency_consistency':
                            if passed:
                                detail_lines.append(f"         {icon} Currency Consistency: All fields consistent")
                            else:
                                detail_lines.append(f"         {icon} Currency Consistency: {actual}")
                        elif check_name == 'subtotal_amount':
                            detail_lines.append(f"         {icon} Subtotal Amount: {message} (expected: {expected})")
                        elif check_name == 'total_amount':
                            detail_lines.append(f"         {icon} Total Amount: {message} (expected: {expected})")
                        elif check_name == 'subtotal_total_match':
                            if passed:
                                detail_lines.append(f"         {icon} Subtotal = Total: Verified")
                            else:
                                detail_lines.append(f"         {icon} Subtotal = Total: Mismatch ({message})")
                        elif check_name == 'product_name':
                            detail_lines.append(f"         {icon} Product Name: '{actual}' (expected: {expected})")
                        elif check_name == 'trial_info':
                            detail_lines.append(f"         {icon} Trial Info: '{actual}' (expected: '{expected}')")
                        elif check_name == 'trial_amount':
                            detail_lines.append(f"         {icon} Trial Amount: '{actual}' (expected: {expected})")
                    
                    # Add header with overall status
                    verify_status = "✓" if overall_verified else "✗"
                    lines.append(f"      {verify_status} Stripe Checkout:")
                    lines.extend(detail_lines)
                
                # 2. User API Verification
                if 'user_api' in verifications:
                    verify_result = verifications['user_api']
                    self._add_api_verification_lines(lines, verify_result, "User API", is_admin=False)
                
                # 3. Admin API Verification
                if 'admin_api' in verifications:
                    verify_result = verifications['admin_api']
                    is_non_blocking = verify_result.get('is_non_blocking', False)
                    self._add_api_verification_lines(lines, verify_result, "Admin API", is_admin=True, is_non_blocking=is_non_blocking)
            
            # Error message if failed
            if not result['passed'] and result.get('error'):
                lines.append(f"  Error: {result['error']}")
        
        lines.append("\n" + "=" * 80)
        
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))
    
    def _add_api_verification_lines(
        self, 
        lines: List[str], 
        verify_result: Dict[str, Any], 
        verify_type: str,
        is_admin: bool = False,
        is_non_blocking: bool = False
    ):
        """
        Helper method to add API verification lines (User API or Admin API)
        
        Args:
            lines: List to append lines to
            verify_result: Verification result dictionary
            verify_type: "User API" or "Admin API"
            is_admin: Whether this is admin API
            is_non_blocking: Whether failures are non-blocking (warnings only)
        """
        if not verify_result.get('verified'):
            # Verification failed
            if is_non_blocking:
                lines.append(f"      ⚠ {verify_type} (webhook-based, may lag):")
                lines.append(f"         Warning: {verify_result.get('message', 'Verification failed')}")
            else:
                lines.append(f"      ✗ {verify_type}:")
                lines.append(f"         Error: {verify_result.get('message', 'Verification failed')}")
            return
        
        # Get subscription data (different keys for user vs admin)
        if is_admin:
            subscription = verify_result.get('admin_subscription', {})
        else:
            subscription = verify_result.get('subscription', {})
        
        # Special case: For refund actions with no subscription (expected behavior)
        # Show simple success message instead of detailed breakdown
        if not subscription:
            message = verify_result.get('message', 'Verified')
            lines.append(f"      ✓ {verify_type}:")
            lines.append(f"         {message}")
            return
        
        # Get granular checks from verifier
        checks = verify_result.get('checks', {})
        
        # Get overall verification status from verifier (TRUST IT!)
        overall_verified = verify_result.get('verified')
        
        # Build display lines from checks
        detail_lines = []
        
        # Display each check that was performed
        check_order = ['status_code', 'plan_code', 'subscription_type', 'trial_period', 'trial_period_dates', 'start_date', 'expire_date']
        
        for check_name in check_order:
            if check_name not in checks:
                continue
                
            check = checks[check_name]
            passed = check.get('passed')
            expected = check.get('expected')
            actual = check.get('actual')
            message = check.get('message', '')
            
            icon = '✓' if passed else '✗'
            
            # Format based on check type
            if check_name == 'status_code':
                detail_lines.append(f"         {icon} Status Code: {actual} (expected: {expected}) - {message}")
            elif check_name == 'plan_code':
                detail_lines.append(f"         {icon} Plan Code: {actual} (expected: {expected})")
            elif check_name == 'subscription_type':
                detail_lines.append(f"         {icon} Subscription Type: {actual} (expected: {expected}) - {message}")
            elif check_name == 'trial_period':
                if expected is not None:
                    detail_lines.append(f"         {icon} Trial Period: {actual} days (expected: {expected} days)")
                else:
                    detail_lines.append(f"         {icon} Trial Period: {message}")
            elif check_name == 'trial_period_dates':
                detail_lines.append(f"         {icon} Trial Period Duration: {actual} (expected: {expected})")
            elif check_name == 'start_date':
                if isinstance(expected, str) and expected.startswith('20'):  # ISO date format
                    detail_lines.append(f"         {icon} Start Date: {actual} (expected: {expected})")
                else:
                    detail_lines.append(f"         {icon} Start Date: {actual} ({message})")
            elif check_name == 'expire_date':
                if passed:
                    detail_lines.append(f"         {icon} Expire Date: {actual} (expected: {expected})")
                else:
                    detail_lines.append(f"         {icon} Expire Date: {actual} (expected: {expected}, {message})")
        
        # Add header with overall status
        if is_non_blocking and not overall_verified:
            verify_status = "⚠"
            header_suffix = " (webhook-based, may lag)"
        else:
            verify_status = "✓" if overall_verified else "✗"
            header_suffix = ""
        
        lines.append(f"      {verify_status} {verify_type}{header_suffix}:")
        lines.extend(detail_lines)
    
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