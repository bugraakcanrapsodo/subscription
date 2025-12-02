"""
Stripe Test Helper
Utilities for managing Stripe test clocks and advancing time for testing
"""

import os
import time
import stripe
from datetime import datetime, timedelta, timezone
from typing import Optional
from base.logger import Logger


class StripeTestHelper:
    """
    Helper class for Stripe subscription time simulation
    Uses Subscription.TestHelpers.advance_clock() to simulate time passing.
    
    This enables testing of:
    - Trial period expirations
    - Subscription renewals
    - Payment retries
    - Status transitions
    
    Note: For subscriptions created through Stripe Checkout (like MLM's),
    we use subscription-level time advancement, not test clocks.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Stripe Test Helper
        
        Args:
            api_key: Stripe test API key (sk_test_...). 
                     If not provided, reads from STRIPE_TEST_API_KEY env var
        """
        self.api_key = api_key or os.getenv('STRIPE_TEST_API_KEY')
        
        if not self.api_key:
            raise ValueError(
                "Stripe API key not provided. "
                "Set STRIPE_TEST_API_KEY environment variable or pass api_key parameter."
            )
        
        if not self.api_key.startswith('sk_test_'):
            raise ValueError("Must use a test mode API key (sk_test_...)")
        
        stripe.api_key = self.api_key
        self.logger = Logger(__name__)
        self.logger.info("Stripe Test Helper initialized")
    
    def get_customer_by_email(self, email: str) -> Optional[dict]:
        """
        Find Stripe customer by email
        
        Note: Searches both regular customers and test clock customers.
        According to Stripe docs: "By default, the List all customers endpoint 
        doesn't include customers with test clocks."
        
        Args:
            email: Customer email address
            
        Returns:
            Customer object or None if not found
        """
        try:
            self.logger.info(f"Searching for Stripe customer with email: {email}")
            
            # First, try regular customer search
            customers = stripe.Customer.list(email=email, limit=1)
            
            if customers.data:
                customer = customers.data[0]
                self.logger.info(f"Found customer (regular): {customer.id}")
                return customer
            
            # If not found, search through test clocks
            # Customers with test clocks don't appear in regular searches!
            self.logger.info(f"Not found in regular search. Checking test clock customers...")
            
            try:
                # List all test clocks
                test_clocks = stripe.test_helpers.TestClock.list(limit=100)
                
                # For each test clock, list its customers
                for clock in test_clocks.data:
                    clock_customers = stripe.Customer.list(
                        test_clock=clock.id,
                        email=email,
                        limit=1
                    )
                    
                    if clock_customers.data:
                        customer = clock_customers.data[0]
                        self.logger.info(f"Found customer (test clock): {customer.id}")
                        self.logger.info(f"  Associated with test clock: {clock.id}")
                        return customer
                
            except Exception as clock_error:
                self.logger.warning(f"Could not search test clock customers: {str(clock_error)}")
            
            self.logger.warning(f"No customer found with email: {email}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding customer: {str(e)}")
            raise
    
    def get_customer_subscriptions(self, customer_id: str) -> list:
        """
        Get all subscriptions for a customer
        
        Args:
            customer_id: Stripe customer ID
            
        Returns:
            List of subscription objects
        """
        try:
            self.logger.info(f"Getting subscriptions for customer: {customer_id}")
            subscriptions = stripe.Subscription.list(customer=customer_id)
            self.logger.info(f"Found {len(subscriptions.data)} subscription(s)")
            return subscriptions.data
        except Exception as e:
            self.logger.error(f"Error getting subscriptions: {str(e)}")
            raise
    
    def advance_time_for_customer_experimental(self, email: str, days: int) -> dict:
        """
        EXPERIMENTAL: Try to advance time using the Dashboard's approach.
        
        Based on reverse-engineering:
        1. Create test clock WITH customer parameter (undocumented)
        2. This retroactively associates the test clock
        3. Advance the test clock
        
        This may fail if the public API doesn't support the 'customer' parameter.
        
        Args:
            email: Customer email
            days: Number of days to advance
            
        Returns:
            Result dict with success status
        """
        try:
            # Find customer
            customer = self.get_customer_by_email(email)
            if not customer:
                raise ValueError(f"Customer not found: {email}")
            
            self.logger.info(f"🧪 EXPERIMENTAL: Trying Dashboard's approach for {customer.id}")
            
            # Calculate target time
            current_time = int(time.time())
            target_time = current_time + (days * 24 * 60 * 60)
            
            # Try to create test clock WITH customer parameter
            try:
                test_clock = self.create_test_clock_for_customer(
                    customer_id=customer.id,
                    frozen_time=target_time,
                    name=f"Test clock for {customer.id}"
                )
                
                self.logger.info(f"✅ Test clock created and associated: {test_clock.id}")
                self.logger.info(f"   Time advanced by {days} days")
                
                # Get updated subscription status
                subscriptions = self.get_customer_subscriptions(customer.id)
                if subscriptions:
                    sub = subscriptions[0]
                    self.logger.info(f"   Subscription status: {sub.status}")
                    
                    return {
                        'success': True,
                        'message': f'Test clock created and advanced by {days} days',
                        'customer_id': customer.id,
                        'test_clock_id': test_clock.id,
                        'subscription_id': sub.id,
                        'new_status': sub.status,
                        'method': 'dashboard_approach',
                        'previous_time': datetime.fromtimestamp(current_time).isoformat(),
                        'new_time': datetime.fromtimestamp(target_time).isoformat()
                    }
                else:
                    return {
                        'success': True,
                        'message': f'Test clock created but no subscription found',
                        'customer_id': customer.id,
                        'test_clock_id': test_clock.id,
                        'method': 'dashboard_approach'
                    }
                    
            except stripe.error.InvalidRequestError as api_error:
                self.logger.error(f"❌ Dashboard approach failed: {api_error.user_message}")
                self.logger.error(f"   The 'customer' parameter is not supported by the public API")
                return {
                    'success': False,
                    'message': f'Stripe API error: {api_error.user_message}',
                    'customer_id': customer.id,
                    'error': 'customer_parameter_not_supported'
                }
                
        except Exception as e:
            self.logger.error(f"Experimental approach failed: {str(e)}")
            return {
                'success': False,
                'message': f'Experimental approach failed: {str(e)}'
            }
    
    def advance_time_for_customer(self, email: str, days: int) -> dict:
        """
        Advance time for a customer's subscription (requires existing test clock).
        
        This method ONLY works if the subscription already has an associated test clock.
        For subscriptions created via Checkout (without test clocks), this will fail.
        
        Use advance_time_for_customer_experimental() to try retroactive test clock association.
        
        Args:
            email: Customer email address
            days: Number of days to advance
            
        Returns:
            dict with status information including:
            - success: bool
            - message: str
            - customer_id: str
            - subscription_id: str
            - test_clock_id: str (if exists)
            - previous_status: str
            - new_status: str
            - method: 'test_clock_advance'
        
        Example:
            >>> helper = StripeTestHelper()
            >>> result = helper.advance_time_for_customer("test@example.com", days=46)
            >>> if result['success']:
            ...     print(f"Status: {result['previous_status']} -> {result['new_status']}")
            >>> else:
            ...     print("No test clock - try advance_time_for_customer_experimental()")
        """
        try:
            # Find customer
            customer = self.get_customer_by_email(email)
            if not customer:
                raise ValueError(f"Customer not found with email: {email}")
            
            # Get customer's subscriptions
            subscriptions = self.get_customer_subscriptions(customer.id)
            
            if not subscriptions:
                self.logger.warning("No subscriptions found for customer")
                return {
                    'success': False,
                    'message': 'No subscriptions found',
                    'customer_id': customer.id
                }
            
            # Get the first active or trialing subscription
            active_sub = None
            for sub in subscriptions:
                if sub.status in ['active', 'trialing']:
                    active_sub = sub
                    break
            
            if not active_sub:
                return {
                    'success': False,
                    'message': 'No active or trialing subscription found',
                    'customer_id': customer.id,
                    'available_subscriptions': [{'id': s.id, 'status': s.status} for s in subscriptions]
                }
            
            previous_status = active_sub.status
            self.logger.info(f"Found subscription: {active_sub.id} (status: {previous_status})")
            
            # Check if subscription has a test clock
            if hasattr(active_sub, 'test_clock') and active_sub.test_clock:
                # Great! The subscription has a test clock - we can actually advance time!
                test_clock_id = active_sub.test_clock
                self.logger.info(f"✅ Subscription has test clock: {test_clock_id}")
                self.logger.info(f"Advancing test clock by {days} days...")
                
                try:
                    # Get current test clock time
                    test_clock = stripe.test_helpers.TestClock.retrieve(test_clock_id)
                    current_time = test_clock.frozen_time
                    target_time = current_time + (days * 24 * 60 * 60)
                    
                    # Advance the test clock
                    stripe.test_helpers.TestClock.advance(
                        test_clock_id,
                        frozen_time=target_time
                    )
                    
                    # Get updated subscription status
                    updated_sub = stripe.Subscription.retrieve(active_sub.id)
                    new_status = updated_sub.status
                    
                    self.logger.info(f"✓ Test clock advanced by {days} days")
                    self.logger.info(f"  Previous status: {previous_status}")
                    self.logger.info(f"  New status: {new_status}")
                    
                    return {
                        'success': True,
                        'message': f'Test clock advanced by {days} days',
                        'customer_id': customer.id,
                        'subscription_id': active_sub.id,
                        'test_clock_id': test_clock_id,
                        'previous_status': previous_status,
                        'new_status': new_status,
                        'previous_time': datetime.fromtimestamp(current_time).isoformat(),
                        'new_time': datetime.fromtimestamp(target_time).isoformat(),
                        'method': 'test_clock_advance'
                    }
                    
                except Exception as clock_error:
                    self.logger.error(f"Failed to advance test clock: {str(clock_error)}")
                    return {
                        'success': False,
                        'message': f'Failed to advance test clock: {str(clock_error)}',
                        'customer_id': customer.id,
                        'subscription_id': active_sub.id,
                        'test_clock_id': test_clock_id
                    }
            
            # No test clock found - subscription was created without one (e.g., via Checkout)
            self.logger.warning("❌ No test clock found for subscription")
            self.logger.warning("   Subscriptions created via Checkout don't have test clocks")
            self.logger.warning("   Use advance_time_for_customer_experimental() to try retroactive association")
            
            return {
                'success': False,
                'message': 'Subscription has no test clock. Cannot advance time.',
                'customer_id': customer.id,
                'subscription_id': active_sub.id,
                'hint': 'Use advance_time_for_customer_experimental() to try Dashboard approach'
            }
                
        except Exception as e:
            self.logger.error(f"Error processing subscription: {str(e)}")
            raise
    
    def advance_test_clock(self, test_clock_id: str, days: int) -> dict:
        """
        Advance an existing test clock by specified number of days.
        
        This method is for subscriptions that were created WITH a test clock.
        If your subscription doesn't have a test clock (like Checkout subscriptions),
        use advance_time_for_customer() instead.
        
        Args:
            test_clock_id: The test clock ID (e.g., 'clock_xxx')
            days: Number of days to advance
            
        Returns:
            dict with status information
            
        Example:
            >>> helper = StripeTestHelper()
            >>> result = helper.advance_test_clock('clock_xxx', days=46)
        """
        try:
            # Retrieve current test clock
            test_clock = stripe.test_helpers.TestClock.retrieve(test_clock_id)
            current_time = test_clock.frozen_time
            
            # Calculate new time
            new_time = current_time + (days * 24 * 60 * 60)
            
            self.logger.info(f"Advancing test clock '{test_clock_id}'")
            self.logger.info(f"  From: {datetime.fromtimestamp(current_time)}")
            self.logger.info(f"  To: {datetime.fromtimestamp(new_time)}")
            
            # Advance the clock
            updated_clock = stripe.test_helpers.TestClock.advance(
                test_clock_id,
                frozen_time=new_time
            )
            
            self.logger.info(f"✓ Test clock advanced by {days} days")
            
            return {
                'success': True,
                'message': f'Test clock advanced by {days} days',
                'test_clock_id': test_clock_id,
                'previous_time': datetime.fromtimestamp(current_time).isoformat(),
                'new_time': datetime.fromtimestamp(new_time).isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Error advancing test clock: {str(e)}")
            return {
                'success': False,
                'message': f'Failed to advance test clock: {str(e)}',
                'test_clock_id': test_clock_id
            }
    
    def create_test_clock_for_customer(self, customer_id: str, frozen_time: Optional[int] = None, name: Optional[str] = None) -> dict:
        """
        EXPERIMENTAL: Try to create a test clock and associate it with an existing customer.
        
        Based on reverse-engineering the Stripe Dashboard, which uses:
        POST /v1/test_helpers/test_clocks
        Body: name=..., frozen_time=..., customer=cus_xxx
        
        This MAY work with the public API if Stripe supports the undocumented 'customer' parameter.
        
        Args:
            customer_id: Existing customer ID (e.g., 'cus_xxx')
            frozen_time: Unix timestamp for clock start (default: now)
            name: Optional name for the test clock
            
        Returns:
            Test clock object if successful
            
        Raises:
            Exception if the parameter is not supported or fails
            
        Example:
            >>> helper = StripeTestHelper()
            >>> customer = helper.get_customer_by_email("test@example.com")
            >>> clock = helper.create_test_clock_for_customer(customer.id)
        """
        try:
            if frozen_time is None:
                frozen_time = int(time.time())
            
            if name is None:
                name = f"Test clock for {customer_id}"
            
            self.logger.info(f"Attempting to create test clock for existing customer: {customer_id}")
            self.logger.info(f"⚠️  Using UNDOCUMENTED 'customer' parameter from Dashboard reverse-engineering")
            
            # Try the Dashboard approach with public API
            test_clock = stripe.test_helpers.TestClock.create(
                frozen_time=frozen_time,
                name=name,
                customer=customer_id  # 👈 UNDOCUMENTED parameter from Dashboard
            )
            
            self.logger.info(f"✅ SUCCESS! Test clock created with customer association: {test_clock.id}")
            self.logger.info(f"   Customer: {customer_id}")
            self.logger.info(f"   Frozen time: {datetime.fromtimestamp(frozen_time)}")
            
            return test_clock
            
        except stripe.error.InvalidRequestError as e:
            self.logger.error(f"❌ Failed: {e.user_message}")
            self.logger.error("The 'customer' parameter is not supported by the public API")
            self.logger.error("Stripe Dashboard uses a private API endpoint")
            raise
        except Exception as e:
            self.logger.error(f"Error creating test clock: {str(e)}")
            raise
    
    def create_test_clock(self, frozen_time: Optional[datetime] = None, name: Optional[str] = None) -> dict:
        """
        Create a new test clock for future use.
        
        IMPORTANT: To use test clocks, you must:
        1. Create the test clock FIRST (this method)
        2. Create customer with test_clock parameter
        3. Create subscription for that customer
        4. Advance the test clock (advance_test_clock method)
        
        This does NOT work with existing subscriptions created via Checkout.
        
        Args:
            frozen_time: Starting time for the clock (default: now)
            name: Optional name for the test clock
            
        Returns:
            Test clock object
            
        Example:
            >>> helper = StripeTestHelper()
            >>> clock = helper.create_test_clock(name="Trial Test")
            >>> # Then create customer with: test_clock=clock.id
        """
        try:
            if frozen_time is None:
                frozen_time = datetime.now()
            
            frozen_timestamp = int(frozen_time.timestamp())
            
            self.logger.info(f"Creating test clock at {frozen_time.isoformat()}")
            
            test_clock = stripe.test_helpers.TestClock.create(
                frozen_time=frozen_timestamp,
                name=name or f"Test clock {frozen_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            self.logger.info(f"✓ Test clock created: {test_clock.id}")
            
            return test_clock
        except Exception as e:
            self.logger.error(f"Error creating test clock: {str(e)}")
            raise
    
    def list_test_clocks(self, limit: int = 10) -> list:
        """
        List all test clocks
        
        Args:
            limit: Maximum number of clocks to return
            
        Returns:
            List of test clock objects
        """
        try:
            self.logger.info(f"Listing test clocks (limit: {limit})")
            clocks = stripe.test_helpers.TestClock.list(limit=limit)
            self.logger.info(f"Found {len(clocks.data)} test clock(s)")
            return clocks.data
        except Exception as e:
            self.logger.error(f"Error listing test clocks: {str(e)}")
            raise
    
    def delete_test_clock(self, test_clock_id: str) -> bool:
        """
        Delete a test clock
        
        Args:
            test_clock_id: Test clock ID
            
        Returns:
            True if successful
        """
        try:
            self.logger.info(f"Deleting test clock: {test_clock_id}")
            stripe.test_helpers.TestClock.delete(test_clock_id)
            self.logger.info(f"✓ Test clock deleted: {test_clock_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error deleting test clock: {str(e)}")
            raise

