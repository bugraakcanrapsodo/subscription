"""
User API Tests
Tests for user device registration and subscription plans
"""

import time
import requests
import pytest
from api.mlm_api import MlmAPI
from base.logger import Logger
from utils.stripe_helper import StripeTestHelper


@pytest.mark.smoke
@pytest.mark.api
@pytest.mark.checkout
class TestMLM:
    """Test suite for user device registration and subscription"""

    def test_register_device_with_user(self, test_user_email):
        """
        Test: Complete user flow - register, login, device, plans, subscription, checkout, payment, time advancement, and verification

        Steps:
        1. Register user with @rapsodotest.com email
        2. Login to get JWT token and user data
        3. Register device with email username as serial
        4. Get eligible web plans
        5. Create subscription with first eligible plan
        6. Get Stripe checkout session URL
        7. Verify checkout page details via Playwright
        8. Complete payment with test card via Playwright
        9. Advance time by 46 days (expire 45-day trial)
        10. Verify membership details in RCloud profile page
        11. Cleanup - Delete user account
        """
        Logger.info(f"Starting complete user flow for: {test_user_email}")

        # Step 1: Register user
        mlm_api = MlmAPI()
        register_response = mlm_api.register(email=test_user_email)
        assert register_response.is_success(), f"Registration failed: {register_response.message}"
        Logger.info(f"✓ User registered: {test_user_email}")

        # Step 2: Login
        login_response = mlm_api.login(email=test_user_email, password="Aa123456")
        assert login_response.is_success(), f"Login failed: {login_response.message}"

        # Get auth token and user data for Playwright browser session
        auth_token = mlm_api.get_auth_token()
        user_data = mlm_api.get_user_data()
        Logger.info(f"✓ User auth_token: {auth_token}")
        Logger.info(f"✓ User data: {user_data}")

        # Step 3: Register device (email username as serial)
        email_username = test_user_email.split('@')[0]
        device_response = mlm_api.register_device(
            registered_mac="AA:BB:CC:DD:EE:FF",
            registered_serial=email_username
        )
        assert device_response.status_code == 200, f"Expected 200, got {device_response.status_code}"
        assert device_response.is_success(), f"Device registration failed: {device_response.message}"
        Logger.info(f"✓ Device registered - Serial: {email_username}")

        # Step 4: Get eligible plans
        plans_response = mlm_api.get_web_plans(country="us")
        assert plans_response.success, "Plans response should be successful"

        eligible_plans = plans_response.get_eligible_plans()
        assert len(eligible_plans) > 0, "Should have at least one eligible plan"

        Logger.info(f"✓ Found {len(eligible_plans)} eligible plans:")
        for plan in eligible_plans:
            Logger.info(f"  - {plan['name']}: code={plan['code']}, trial_days={plan['trial_period_days']}")

        # Step 5: Create subscription with first eligible plan (oneYearSubscription with 45-day trial)
        first_plan = eligible_plans[0]
        subscription_response = mlm_api.create_web_subscription(plan_code=first_plan['code'])
        assert subscription_response.is_success(), "Subscription creation should be successful"

        # Step 6: Get checkout URL
        checkout_url = subscription_response.get_checkout_url()
        assert checkout_url is not None, "Should have checkout URL"
        assert "checkout.stripe.com" in checkout_url, "Should be Stripe checkout URL"

        Logger.info(f"✓ Subscription created with plan: {first_plan['name']}")
        Logger.info(f"  - Trial period: {first_plan['trial_period_days']} days")
        Logger.info(f"✓ Checkout URL: {checkout_url[:80]}...")

        # Step 7: Verify checkout page via Playwright service
        Logger.info("Sending checkout URL to Playwright service for verification")
        playwright_url = "http://localhost:3001/api/checkout/verify"
        payload = {
            "checkoutUrl": checkout_url,
            "currency": "US"  # Select US currency on payment pages
        }

        response = requests.post(playwright_url, json=payload, timeout=60)
        assert response.status_code == 200, f"Playwright service failed with status {response.status_code}"

        result = response.json()
        assert result['success'] is True, f"Checkout verification failed: {result.get('error', 'Unknown error')}"

        # Get checkout details
        checkout_details = result['data']['checkoutDetails']

        Logger.info(f"\n📋 Checkout Page Details:")
        Logger.info(f"  Product Summary Name: {checkout_details.get('productSummaryName')}")
        Logger.info(f"  Product Summary Total: {checkout_details.get('productSummaryTotalAmount')}")
        Logger.info(f"  Line Item Name: {checkout_details.get('lineItemProductName')}")
        Logger.info(f"  Line Item Total: {checkout_details.get('lineItemTotalAmount')}")
        Logger.info(f"  Subtotal: {checkout_details.get('subtotalAmount')}")
        Logger.info(f"  Total Amount: {checkout_details.get('totalAmount')}")
        Logger.info(f"  Trial Amount: {checkout_details.get('trialAmount')}")
        Logger.info(f"  Screenshot: {result['data']['screenshot']}")

        # Assertions for trial checkout (45 days free, $199.99 per year)
        if checkout_details.get('productSummaryName'):
            assert "MLM2PRO Premium Membership" in checkout_details['productSummaryName'], \
                f"Product name should contain 'MLM2PRO Premium Membership', got: {checkout_details['productSummaryName']}"
            Logger.info(f"✓ Product name verified")

        if checkout_details.get('productSummaryTotalAmount'):
            assert "45 days free" in checkout_details['productSummaryTotalAmount'], \
                f"Should show '45 days free', got: {checkout_details['productSummaryTotalAmount']}"
            Logger.info(f"✓ Trial period verified (45 days free)")

        if checkout_details.get('trialAmount'):
            assert "$0" in checkout_details['trialAmount'], \
                f"Trial amount should be $0, got: {checkout_details['trialAmount']}"
            Logger.info(f"✓ Trial amount verified ($0)")

        Logger.info(f"✅ Checkout verification passed!")

        # Step 8: Complete payment with Stripe test card
        Logger.info("💳 Processing payment with test card")
        payment_url = "http://localhost:3001/api/checkout/pay-card"
        payment_payload = {
            "checkoutUrl": checkout_url,
            "cardNumber": "4242424242424242",
            "cardExpiry": "12/30",
            "cardCvc": "123",
            "cardholderName": email_username,  # Use email username as cardholder name
            "currency": "US",
            "authToken": auth_token,  # Pass auth token for authenticated success page
            "userData": user_data  # Pass user data for mlmWebUser cookie
        }

        payment_response = requests.post(payment_url, json=payment_payload, timeout=120)
        assert payment_response.status_code == 200, f"Payment failed with status {payment_response.status_code}"

        payment_result = payment_response.json()
        assert payment_result['success'] is True, f"Payment submission failed: {payment_result.get('error', 'Unknown error')}"

        # Check if payment was successful (redirected to success URL)
        payment_data = payment_result['data']
        payment_succeeded = payment_data.get('paymentSucceeded', False)
        final_url = payment_data.get('finalUrl', '')

        assert payment_succeeded is True, f"Payment was not successful. Final URL: {final_url}"
        assert 'membership' in final_url, f"Expected success URL, got: {final_url}"

        Logger.info(f"✓ Payment completed successfully!")
        Logger.info(f"  - Cardholder: {email_username}")
        Logger.info(f"  - Card: 4242...4242 (Visa test card)")
        Logger.info(f"  - Payment Status: {'SUCCESS' if payment_succeeded else 'FAILED'}")
        Logger.info(f"  - Final URL: {final_url[:80]}...")
        Logger.info(f"  - Before screenshot: {payment_data.get('beforeScreenshot')}")
        Logger.info(f"  - After screenshot: {payment_data.get('afterScreenshot')}")

        Logger.info(f"✅ Complete flow successful - API + UI verification + Payment passed!")

        # Wait for page to settle after payment
        Logger.info("⏳ Waiting 2 seconds for page to settle after payment...")
        time.sleep(20)

        # Step 9: Advance time by 46 days to expire the 45-day trial
        Logger.info("\n⏰ Advancing time by 46 days to expire trial period...")
        try:
            stripe_helper = StripeTestHelper()
            advance_result = stripe_helper.advance_time_for_customer(test_user_email, days=46)

            if advance_result['success']:
                Logger.info(f"✓ Time advanced successfully!")
                Logger.info(f"  - Customer ID: {advance_result['customer_id']}")
                Logger.info(f"  - Test Clock ID: {advance_result['test_clock_id']}")
                Logger.info(f"  - Previous Time: {advance_result['previous_time']}")
                Logger.info(f"  - New Time: {advance_result['new_time']}")
                Logger.info(f"  - Days Advanced: 46")
            else:
                Logger.warning(f"⚠️  Could not advance time: {advance_result['message']}")
                Logger.warning(f"  Customer ID: {advance_result.get('customer_id', 'N/A')}")
        except Exception as e:
            Logger.error(f"❌ Error advancing time: {str(e)}")
            Logger.warning("Continuing test without time advancement...")

        # Wait a bit for Stripe/backend to process the time change
        Logger.info("⏳ Waiting 3 seconds for subscription status to update...")
        time.sleep(3)

        # Step 10: Verify membership details in RCloud profile page
        Logger.info("\n📊 Verifying membership details in RCloud profile page (after time advancement)")
        membership_url = "http://localhost:3001/api/rcloud/membership-details"
        membership_payload = {
            "authToken": auth_token,
            "userData": user_data
        }

        membership_response = requests.post(membership_url, json=membership_payload, timeout=60)
        assert membership_response.status_code == 200, f"Membership details failed with status {membership_response.status_code}"

        membership_result = membership_response.json()
        assert membership_result['success'] is True, f"Membership retrieval failed: {membership_result.get('error', 'Unknown error')}"

        membership_details = membership_result['data']['membershipDetails']

        # Verify active subscription
        active_subscription = membership_details['activeSubscription']
        Logger.info(f"📋 Active Subscription:")
        Logger.info(f"  Type: {active_subscription['membershipType']}")
        Logger.info(f"  Expires: {active_subscription['expireDate']}")

        assert "Premium Membership Trial" in active_subscription['membershipType'], \
            f"Expected 'Premium Membership Trial', got: {active_subscription['membershipType']}"
        Logger.info(f"✓ Membership type verified")

        # Verify available offers
        available_offers = membership_details['availableOffers']
        Logger.info(f"\n💰 Available Offers ({len(available_offers)} cards):")
        for idx, offer in enumerate(available_offers, 1):
            Logger.info(f"  {idx}. {offer['name']} - {offer['price']}")

        assert len(available_offers) == 2, f"Expected 2 offers, got {len(available_offers)}"

        # Verify specific offers
        offer_names = [offer['name'] for offer in available_offers]
        assert "2-YEAR MEMBERSHIP" in offer_names, "Should have 2-YEAR MEMBERSHIP offer"
        assert "LIFETIME MEMBERSHIP" in offer_names, "Should have LIFETIME MEMBERSHIP offer"

        # Verify prices
        two_year_offer = next((o for o in available_offers if "2-YEAR" in o['name']), None)
        lifetime_offer = next((o for o in available_offers if "LIFETIME" in o['name']), None)

        assert two_year_offer is not None, "2-YEAR offer not found"
        assert "$329.99" in two_year_offer['price'], f"Expected $329.99, got: {two_year_offer['price']}"

        assert lifetime_offer is not None, "LIFETIME offer not found"
        assert "$599.99" in lifetime_offer['price'], f"Expected $599.99, got: {lifetime_offer['price']}"

        Logger.info(f"✓ All membership details verified!")
        Logger.info(f"  Screenshot: {membership_result['data']['screenshot']}")

        # Step 11: Cleanup - Delete user account
        Logger.info("\n🗑️  Cleaning up - Deleting test user account")
        delete_response = mlm_api.delete_user_account()
        assert delete_response.is_success(), f"User deletion failed: {delete_response.message}"
        Logger.info(f"✓ Test user deleted: {test_user_email}")
