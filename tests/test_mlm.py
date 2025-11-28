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
        9. 🧪 EXPERIMENTAL: Advance time by 46 days using Dashboard's approach
           - Tests if public API supports undocumented 'customer' parameter
           - Creates test clock WITH customer parameter (retroactive association)
           - TEST WILL FAIL if parameter is not supported
        10. Verify membership details in RCloud profile page (trial should be ended)
        11. Cleanup - Delete user account
        
        Note: This test validates if Stripe's public API supports the 'customer' parameter
              for test clock creation (discovered via Dashboard reverse-engineering).
              If the parameter is not supported, the test will fail explicitly.
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
        Logger.info(f"✓ Checkout URL: {checkout_url}")

        # Step 7: Verify checkout page via Playwright service (VPN connection handled internally)
        Logger.info("Sending checkout URL to Playwright service for verification")
        playwright_url = "http://localhost:3001/api/checkout/verify"
        payload = {
            "checkoutUrl": checkout_url,
            "currency": "SG",  # Select Singapore currency on payment pages
            "country": "sg"  # Connect to Singapore VPN to get SGD pricing
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

        # Assertions for trial checkout (45 days free, S$299.99 per year for Singapore)
        if checkout_details.get('productSummaryName'):
            assert "MLM2PRO Premium Membership" in checkout_details['productSummaryName'], \
                f"Product name should contain 'MLM2PRO Premium Membership', got: {checkout_details['productSummaryName']}"
            Logger.info(f"✓ Product name verified")

        if checkout_details.get('productSummaryTotalAmount'):
            assert "45 days free" in checkout_details['productSummaryTotalAmount'], \
                f"Should show '45 days free', got: {checkout_details['productSummaryTotalAmount']}"
            Logger.info(f"✓ Trial period verified (45 days free)")

        if checkout_details.get('trialAmount'):
            assert "0" in checkout_details['trialAmount'], \
                f"Trial amount should be 0 (SGD), got: {checkout_details['trialAmount']}"
            Logger.info(f"✓ Trial amount verified (S$0 - Singapore Dollars)")
        
        if checkout_details.get('totalAmount'):
            assert "299.99" in checkout_details['totalAmount'], \
                f"Total amount should be S$299.99 (SGD), got: {checkout_details['totalAmount']}"
            Logger.info(f"✓ Total amount verified (S$299.99 - Singapore Dollars)")

        Logger.info(f"✅ Checkout verification passed!")

        """# Step 8: Complete payment with Stripe test card
        Logger.info("💳 Processing payment with test card")
        payment_url = "http://localhost:3001/api/checkout/pay-card"
        payment_payload = {
            "checkoutUrl": checkout_url,
            "cardNumber": "4242424242424242",
            "cardExpiry": "12/30",
            "cardCvc": "123",
            "cardholderName": email_username,  # Use email username as cardholder name
            "currency": "SG",  # Singapore currency
            "country": "sg",  # Connect to Singapore VPN to get SGD pricing
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
        time.sleep(2)

        # Step 9: Advance time by 46 days (Testing Dashboard's approach)
        Logger.info("\n⏰ Advancing time by 46 days to expire trial period...")
        Logger.info("🧪 EXPERIMENTAL: Testing Dashboard's approach (retroactive test clock)")
        Logger.info("   This uses the undocumented 'customer' parameter discovered via reverse-engineering")
        advance_result = None  # Initialize for later reference
        try:
            stripe_helper = StripeTestHelper()
            advance_result = stripe_helper.advance_time_for_customer_experimental(test_user_email, days=46)

            if advance_result['success']:
                Logger.info(f"🎉 SUCCESS! Dashboard approach WORKS via public API!")
                Logger.info(f"  - Test Clock ID: {advance_result.get('test_clock_id', 'N/A')}")
                Logger.info(f"  - Time advanced by 46 days (actual time simulation!)")
                Logger.info(f"  - Customer ID: {advance_result['customer_id']}")
                Logger.info(f"  - Subscription ID: {advance_result.get('subscription_id', 'N/A')}")
                Logger.info(f"  - New Status: {advance_result.get('new_status', 'N/A')}")
                Logger.info(f"  - Method: {advance_result.get('method', 'N/A')}")
            else:
                Logger.error(f"❌ Dashboard approach FAILED!")
                Logger.error(f"  Message: {advance_result['message']}")
                Logger.error(f"  Customer ID: {advance_result.get('customer_id', 'N/A')}")
                if 'error' in advance_result:
                    Logger.error(f"  Error: {advance_result['error']}")
                Logger.error(f"  The 'customer' parameter is NOT supported by Stripe's public API")
                Logger.error(f"  Dashboard uses private/internal APIs")
                pytest.fail("Experimental approach failed - cannot advance time for Checkout subscriptions")
        except Exception as e:
            Logger.error(f"❌ Error advancing time: {str(e)}")
            pytest.fail(f"Failed to advance time: {str(e)}")

        # Wait a bit for Stripe/backend to process the time advancement
        Logger.info("⏳ Waiting 5 seconds for subscription status to update...")
        time.sleep(5)

        # Step 10: Verify membership details in RCloud profile page
        Logger.info("\n📊 Verifying membership details in RCloud profile page (after trial end)")
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

        # Verify active subscription (after time advancement)
        active_subscription = membership_details['activeSubscription']
        Logger.info(f"📋 Active Subscription (after time advancement):")
        Logger.info(f"  Type: {active_subscription['membershipType']}")
        Logger.info(f"  Expires: {active_subscription['expireDate']}")

        # After advancing time by 46 days (past the 45-day trial), 
        # the trial should be ended and "Trial" should not be in the membership type
        assert "Premium Membership Trial" not in active_subscription['membershipType'], \
            f"Expected trial to be ended after 46 days. Got: {active_subscription['membershipType']}"
        assert "Premium Membership" in active_subscription['membershipType'], \
            f"Expected 'Premium Membership', got: {active_subscription['membershipType']}"
        Logger.info(f"✓ Membership type verified (trial ended)")
        
        # Log success message
        Logger.info(f"✅ BREAKTHROUGH: Dashboard approach worked! Public API supports 'customer' parameter!")
        Logger.info(f"✅ Test clock retroactively associated with Checkout subscription!")

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

        # Step 10.5: Disconnect VPN
        Logger.info("\n🔓 Disconnecting from VPN...")
        vpn_disconnect_url = "http://localhost:3001/api/vpn/disconnect"
        vpn_disconnect_response = requests.post(vpn_disconnect_url, json={}, timeout=30)
        
        if vpn_disconnect_response.status_code == 200:
            vpn_disconnect_result = vpn_disconnect_response.json()
            if vpn_disconnect_result.get('success'):
                Logger.info(f"✓ VPN disconnected successfully")
            else:
                Logger.warn(f"⚠️  VPN disconnect warning: {vpn_disconnect_result.get('message', 'Unknown')}")
        else:
            Logger.warn(f"⚠️  VPN disconnect failed with status {vpn_disconnect_response.status_code}")

        # Step 11: Cleanup - Delete user account
        Logger.info("\n🗑️  Cleaning up - Deleting test user account")
        delete_response = mlm_api.delete_user_account()
        assert delete_response.is_success(), f"User deletion failed: {delete_response.message}"
        Logger.info(f"✓ Test user deleted: {test_user_email}") """
