"""
Stripe Test Helper
Utilities for managing Stripe test clocks and advancing time for testing
"""

import os
import stripe
from datetime import datetime, timedelta
from typing import Optional
from base.logger import Logger


class StripeTestHelper:
    """
    Helper class for Stripe test clock operations
    Enables time-based subscription testing
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
        
        Args:
            email: Customer email address
            
        Returns:
            Customer object or None if not found
        """
        try:
            self.logger.info(f"Searching for Stripe customer with email: {email}")
            customers = stripe.Customer.list(email=email, limit=1)
            
            if customers.data:
                customer = customers.data[0]
                self.logger.info(f"Found customer: {customer.id}")
                return customer
            else:
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
    
    def advance_time_for_customer(self, email: str, days: int) -> dict:
        """
        Advance time for a customer by specified number of days
        This will trigger trial expirations, renewals, etc.
        
        Args:
            email: Customer email address
            days: Number of days to advance
            
        Returns:
            dict with status information
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
            
            # Check if customer has a test clock
            if hasattr(customer, 'test_clock') and customer.test_clock:
                test_clock_id = customer.test_clock
                self.logger.info(f"Customer has test clock: {test_clock_id}")
                
                # Get current test clock time
                test_clock = stripe.test_helpers.TestClock.retrieve(test_clock_id)
                current_time = test_clock.frozen_time
                
                # Calculate new time
                new_time = current_time + (days * 24 * 60 * 60)
                
                self.logger.info(f"Advancing test clock from {datetime.fromtimestamp(current_time)} to {datetime.fromtimestamp(new_time)}")
                
                # Advance the test clock
                updated_clock = stripe.test_helpers.TestClock.advance(
                    test_clock_id,
                    frozen_time=new_time
                )
                
                self.logger.info(f"✓ Test clock advanced by {days} days")
                
                return {
                    'success': True,
                    'message': f'Test clock advanced by {days} days',
                    'customer_id': customer.id,
                    'test_clock_id': test_clock_id,
                    'previous_time': datetime.fromtimestamp(current_time).isoformat(),
                    'new_time': datetime.fromtimestamp(new_time).isoformat()
                }
            else:
                # Customer doesn't have a test clock - use subscription directly
                self.logger.warning("Customer does not have a test clock. Cannot advance time programmatically.")
                
                # For customers without test clocks, we can't advance time
                # This typically happens when subscriptions are created without test clock
                return {
                    'success': False,
                    'message': 'Customer does not have a test clock. Subscription was not created with a test clock.',
                    'customer_id': customer.id,
                    'subscriptions': [sub.id for sub in subscriptions]
                }
                
        except Exception as e:
            self.logger.error(f"Error advancing time: {str(e)}")
            raise
    
    def create_test_clock(self, frozen_time: Optional[datetime] = None, name: Optional[str] = None) -> dict:
        """
        Create a new test clock
        
        Args:
            frozen_time: Starting time for the clock (default: now)
            name: Optional name for the test clock
            
        Returns:
            Test clock object
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

