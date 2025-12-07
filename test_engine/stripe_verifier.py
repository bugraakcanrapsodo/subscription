"""
Stripe Checkout Verifier
Verifies Stripe checkout page details including prices and currency
"""

import json
import requests
from typing import Dict, Any, Optional
from pathlib import Path
from base.logger import Logger


class StripeCheckoutVerifier:
    """
    Verify Stripe checkout page details
    """
    
    def __init__(self, playwright_service_url: str = "http://localhost:3001"):
        """
        Initialize Stripe checkout verifier
        
        Args:
            playwright_service_url: URL of the Playwright service
        """
        self.playwright_service_url = playwright_service_url
        self.logger = Logger(__name__)
        
        # Load subscription configurations for price lookup
        subscriptions_path = Path(__file__).parent.parent / 'config' / 'subscriptions.json'
        with open(subscriptions_path, 'r') as f:
            self.subscriptions_config = json.load(f)
    
    def verify_checkout_page_gui(
        self,
        checkout_url: str,
        subscription_type: str,
        currency: str = 'usd',
        trial_eligible: bool = True,
        country: str = 'us'
    ) -> Dict[str, Any]:
        """
        Verify Stripe checkout page via GUI (Playwright) - checks price and details
        
        Args:
            checkout_url: Stripe checkout URL
            subscription_type: Subscription type (e.g., '1y_premium')
            currency: Currency code (e.g., 'usd', 'cad', 'aud')
            trial_eligible: Whether user is trial eligible
            country: Country code for VPN connection (e.g., 'us', 'jp', 'de')
            
        Returns:
            Verification result dictionary
        """
        self.logger.info(f"Verifying Stripe checkout page for {subscription_type} in {currency.upper()}")
        
        # Get subscription config
        subscription_config = self.subscriptions_config.get(subscription_type)
        if not subscription_config:
            return {
                'verified': False,
                'message': f'Subscription type not found: {subscription_type}'
            }
        
        # Get expected price for currency
        prices = subscription_config.get('prices', {})
        expected_price = prices.get(currency.lower())
        
        if expected_price is None:
            return {
                'verified': False,
                'message': f'Price not configured for currency: {currency}'
            }
        
        # Get currency info
        currencies = self.subscriptions_config.get('currencies', {})
        currency_info = currencies.get(currency.lower(), {})
        
        try:
            # Call Playwright service to verify checkout page
            payload = {
                'checkoutUrl': checkout_url,
                'currency': currency.lower(),
                'country': country.lower()
            }
            
            self.logger.info(f"Calling Playwright service to verify checkout page...")
            self.logger.info(f"  VPN Country: {country.upper()}, Currency: {currency.upper()}")
            
            response = requests.post(
                f'{self.playwright_service_url}/api/checkout/verify',
                json=payload,
                timeout=60
            )
            
            # Log full response from Docker Playwright service
            self.logger.info(f"Playwright Service Response (checkout/verify):")
            self.logger.info(f"  Status Code: {response.status_code}")
            self.logger.debug(f"  Full Response: {response.text}")
            
            if response.status_code != 200:
                self.logger.error(f"Playwright service returned non-200 status: {response.status_code}")
                return {
                    'verified': False,
                    'message': f'Playwright service error: {response.status_code}',
                    'response': response.text
                }
            
            result = response.json()
            self.logger.info(f"  Success: {result.get('success')}")
            self.logger.info(f"  Message: {result.get('message')}")
            
            # Log VPN location verification if available
            vpn_verification = result.get('vpnLocationVerification')
            if vpn_verification:
                self.logger.info(f"VPN Location Verification:")
                if vpn_verification.get('success'):
                    self.logger.info(f"  ✓ Verified: External IP is from {vpn_verification.get('detectedCountry', 'unknown').upper()}")
                    self.logger.info(f"  IP: {vpn_verification.get('ip', 'N/A')}, City: {vpn_verification.get('city', 'N/A')}, {vpn_verification.get('region', 'N/A')}")
                else:
                    self.logger.warning(f"  ✗ Location Mismatch: Expected {vpn_verification.get('expectedCountry', 'unknown').upper()}, Got {vpn_verification.get('detectedCountry', 'unknown').upper()}")
                    self.logger.warning(f"  IP: {vpn_verification.get('ip', 'N/A')}, City: {vpn_verification.get('city', 'N/A')}")
                    self.logger.warning(f"  This may cause currency/pricing mismatches!")
            
            checkout_details = result.get('data', {}).get('checkoutDetails', {})
            
            self.logger.info(f"Checkout page details retrieved:")
            self.logger.info(f"  Product Name: {checkout_details.get('productSummaryName')}")
            self.logger.info(f"  Total Amount: {checkout_details.get('totalAmount')}")
            self.logger.info(f"  Trial Amount: {checkout_details.get('trialAmount')}")
            
            # Extract currency from all amount fields to ensure consistency
            subtotal_amount_str = checkout_details.get('subtotalAmount', '')
            total_amount_str = checkout_details.get('totalAmount', '')
            trial_amount_str = checkout_details.get('trialAmount', '')
            
            # Extract currency from totalAmount as primary
            actual_currency = self._extract_currency_from_amount(total_amount_str, currency).lower()
            
            # Also extract from subtotal and trial to verify consistency
            subtotal_currency = self._extract_currency_from_amount(subtotal_amount_str, currency).lower()
            trial_currency = self._extract_currency_from_amount(trial_amount_str, currency).lower()
            
            self.logger.info(f"  Extracted Currencies:")
            self.logger.info(f"    Total: {actual_currency.upper()}")
            self.logger.info(f"    Subtotal: {subtotal_currency.upper()}")
            self.logger.info(f"    Trial: {trial_currency.upper()}")
            self.logger.info(f"  Expected: {currency.upper()}")
            
            # Initialize granular checks dictionary
            checks = {}
            verification_issues = []
            
            # Verify primary currency matches expected
            currency_passed = actual_currency == currency.lower()
            checks['currency'] = {
                'passed': currency_passed,
                'expected': currency.upper(),
                'actual': actual_currency.upper(),
                'message': f'{actual_currency.upper()}'
            }
            
            if not currency_passed:
                verification_issues.append(f'Currency mismatch: expected {currency.upper()}, got {actual_currency.upper()}')
            else:
                self.logger.info(f"✓ Currency verified: {actual_currency.upper()} (expected: {currency.upper()})")
            
            # Extract and verify all amount fields
            actual_subtotal_amount_str = checkout_details.get('subtotalAmount', '')
            actual_total_amount_str = checkout_details.get('totalAmount', '')
            
            actual_subtotal_price = None
            actual_total_price = None
            
            if actual_subtotal_amount_str:
                actual_subtotal_price = self._extract_price_from_string(actual_subtotal_amount_str, currency_info)
            
            if actual_total_amount_str:
                actual_total_price = self._extract_price_from_string(actual_total_amount_str, currency_info)
            
            # Verify subtotal amount
            if actual_subtotal_price is None:
                checks['subtotal_amount'] = {
                    'passed': False,
                    'expected': expected_price,
                    'actual': None,
                    'message': f'Could not extract from "{actual_subtotal_amount_str}"'
                }
                verification_issues.append(f'Could not extract subtotal amount from "{actual_subtotal_amount_str}"')
            else:
                subtotal_passed = abs(actual_subtotal_price - expected_price) <= 0.01
                checks['subtotal_amount'] = {
                    'passed': subtotal_passed,
                    'expected': expected_price,
                    'actual': actual_subtotal_price,
                    'message': f'{actual_subtotal_amount_str}'
                }
                
                if not subtotal_passed:
                    verification_issues.append(f'Subtotal amount mismatch: expected {expected_price}, got {actual_subtotal_price}')
                else:
                    self.logger.info(f"✓ Subtotal amount verified: {actual_subtotal_price} (expected: {expected_price})")
            
            # Verify total amount
            if actual_total_price is None:
                checks['total_amount'] = {
                    'passed': False,
                    'expected': expected_price,
                    'actual': None,
                    'message': f'Could not extract from "{actual_total_amount_str}"'
                }
                verification_issues.append(f'Could not extract total amount from "{actual_total_amount_str}"')
            else:
                total_passed = abs(actual_total_price - expected_price) <= 0.01
                checks['total_amount'] = {
                    'passed': total_passed,
                    'expected': expected_price,
                    'actual': actual_total_price,
                    'message': f'{actual_total_amount_str}'
                }
                
                if not total_passed:
                    verification_issues.append(f'Total amount mismatch: expected {expected_price}, got {actual_total_price}')
                else:
                    self.logger.info(f"✓ Total amount verified: {actual_total_price} (expected: {expected_price})")
            
            # Verify product name contains expected membership name
            actual_product_name = checkout_details.get('productSummaryName', '')
            expected_product_name = subscription_config.get('description', '')
            
            # Verify product name
            # Stripe might add "Try " prefix for trial products (e.g., "Try MLM2PRO Premium Membership")
            # So we check if the expected name is contained in the actual name
            product_passed = expected_product_name in actual_product_name
            checks['product_name'] = {
                'passed': product_passed,
                'expected': f'contains "{expected_product_name}"',
                'actual': actual_product_name,
                'message': f'"{actual_product_name}"'
            }
            
            if not product_passed:
                verification_issues.append(f'Product name mismatch: expected to contain "{expected_product_name}", got "{actual_product_name}"')
            else:
                self.logger.info(f"✓ Product name verified: '{actual_product_name}' contains '{expected_product_name}'")
            
            # Verify currency consistency across all amount fields
            supports_trial = subscription_config.get('supports_trial', False)
            if supports_trial and trial_eligible:
                # For trial users: check total, subtotal, AND trial currency
                all_currencies = [actual_currency, subtotal_currency, trial_currency]
                unique_currencies = set(c for c in all_currencies if c)
                currency_consistent = len(unique_currencies) == 1
                
                checks['currency_consistency'] = {
                    'passed': currency_consistent,
                    'expected': 'all fields use same currency',
                    'actual': f'total:{actual_currency.upper()}, subtotal:{subtotal_currency.upper()}, trial:{trial_currency.upper()}',
                    'message': 'consistent' if currency_consistent else f'inconsistent: {unique_currencies}'
                }
                
                if not currency_consistent:
                    verification_issues.append(f'Currency inconsistency: total={actual_currency.upper()}, subtotal={subtotal_currency.upper()}, trial={trial_currency.upper()}')
                else:
                    self.logger.info(f"✓ Currency consistent across all fields (total, subtotal, trial)")
            else:
                # For non-trial users: check only total and subtotal currency
                all_currencies = [actual_currency, subtotal_currency]
                unique_currencies = set(c for c in all_currencies if c)
                currency_consistent = len(unique_currencies) == 1
                
                checks['currency_consistency'] = {
                    'passed': currency_consistent,
                    'expected': 'all fields use same currency',
                    'actual': f'total:{actual_currency.upper()}, subtotal:{subtotal_currency.upper()}',
                    'message': 'consistent' if currency_consistent else f'inconsistent: {unique_currencies}'
                }
                
                if not currency_consistent:
                    verification_issues.append(f'Currency inconsistency: total={actual_currency.upper()}, subtotal={subtotal_currency.upper()}')
                else:
                    self.logger.info(f"✓ Currency consistent between total and subtotal")
            
            # Verify trial-specific information if applicable
            actual_trial_text = None
            expected_trial_text = None
            
            if supports_trial and trial_eligible:
                trial_days = subscription_config.get('trial_period_days', 0)
                trial_amount = checkout_details.get('trialAmount', '')
                product_summary = checkout_details.get('productSummaryTotalAmount', '')
                
                expected_trial_text = f"{trial_days} days free"
                actual_trial_text = product_summary
                
                # Verify trial text in product summary
                trial_text_passed = f'{trial_days} days free' in product_summary.lower()
                checks['trial_info'] = {
                    'passed': trial_text_passed,
                    'expected': expected_trial_text,
                    'actual': product_summary,
                    'message': f'"{product_summary}"'
                }
                
                if not trial_text_passed:
                    verification_issues.append(f'Trial info mismatch: expected "{expected_trial_text}", got "{product_summary}"')
                else:
                    self.logger.info(f"✓ Trial info verified: {trial_days} days free")
                
                # Verify trial amount is $0
                trial_amount_passed = '0' in trial_amount if trial_amount else False
                checks['trial_amount'] = {
                    'passed': trial_amount_passed,
                    'expected': '$0.00',
                    'actual': trial_amount,
                    'message': f'"{trial_amount}"'
                }
                
                if not trial_amount_passed:
                    verification_issues.append(f'Trial amount should be $0, got "{trial_amount}"')
                else:
                    self.logger.info(f"✓ Trial amount verified: {trial_amount}")
            
            # Return verification result with granular checks
            if verification_issues:
                return {
                    'verified': False,
                    'message': '; '.join(verification_issues),
                    'issues': verification_issues,
                    'checks': checks
                }
            else:
                return {
                    'verified': True,
                    'message': 'Stripe checkout page verified successfully',
                    'checks': checks
                }
        
        except requests.exceptions.Timeout:
            return {
                'verified': False,
                'message': 'Timeout verifying Stripe checkout page'
            }
        except Exception as e:
            self.logger.error(f"Error verifying checkout page: {str(e)}")
            return {
                'verified': False,
                'message': f'Error: {str(e)}',
                'error': str(e)
            }
    
    def _extract_currency_from_amount(self, amount_str: str, expected_currency: str = 'usd') -> str:
        """
        Extract currency code from amount string
        
        Args:
            amount_str: Amount string like "CA$249.99", "¥29,800", or "US$199.99"
            expected_currency: Expected currency code (default: 'usd')
            
        Returns:
            Currency code (e.g., 'usd', 'jpy', 'cad')
        """
        if not amount_str:
            return expected_currency
        
        # Currency mapping from symbols/prefixes to codes
        currency_map = {
            'US$': 'usd',
            'CA$': 'cad',
            'A$': 'aud',
            'S$': 'sgd',
            '$': 'usd',  # Default $ to USD
            '€': 'eur',
            '£': 'gbp',
            '¥': 'jpy'
        }
        
        # Check for currency prefix/symbol
        for symbol, code in currency_map.items():
            if amount_str.startswith(symbol) or symbol in amount_str:
                return code
        
        # If no match, return expected currency
        return expected_currency
    
    def _extract_price_from_string(self, amount_str: str, currency_info: Dict) -> Optional[float]:
        """
        Extract numeric price from formatted string
        
        Args:
            amount_str: Amount string like "CA$249.99", "US$199.99", or "¥29,800"
            currency_info: Currency configuration
            
        Returns:
            Float price or None if parsing fails
        """
        try:
            self.logger.debug(f"Extracting price from: '{amount_str}'")
            
            # Extract ONLY digits, dots, and commas
            clean_str = ''.join(c for c in amount_str if c.isdigit() or c in '.,')
            
            # Remove thousands separators (commas)
            clean_str = clean_str.replace(',', '')
            
            self.logger.debug(f"After extracting digits/dots/commas: '{clean_str}'")
            
            if not clean_str:
                self.logger.error(f"No numeric value found in '{amount_str}'")
                return None
            
            # Convert to float
            price = float(clean_str)
            self.logger.info(f"✓ Extracted price: {price} from '{amount_str}'")
            return price
        
        except Exception as e:
            self.logger.error(f"Failed to parse amount '{amount_str}': {str(e)}")
            return None
    
    def get_expected_price_string(
        self,
        subscription_type: str,
        currency: str
    ) -> Optional[str]:
        """
        Get formatted price string for a subscription in a currency
        
        Args:
            subscription_type: Subscription type
            currency: Currency code
            
        Returns:
            Formatted price string (e.g., "CA$249.99", "¥29,800")
        """
        subscription_config = self.subscriptions_config.get(subscription_type)
        if not subscription_config:
            return None
        
        prices = subscription_config.get('prices', {})
        price = prices.get(currency.lower())
        
        if price is None:
            return None
        
        # Get currency format
        currencies = self.subscriptions_config.get('currencies', {})
        currency_info = currencies.get(currency.lower(), {})
        format_str = currency_info.get('format', '${amount}')
        
        # Format price based on currency
        decimal_places = currency_info.get('decimal_places', 2)
        
        if decimal_places == 0:
            # JPY - no decimals, add thousands separator
            formatted_price = f'{int(price):,}'
        else:
            # Other currencies - 2 decimal places
            formatted_price = f'{price:.2f}'
        
        return format_str.replace('{amount}', formatted_price)

