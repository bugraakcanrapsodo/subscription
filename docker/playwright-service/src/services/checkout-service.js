const BaseService = require('./base-service');
const CheckoutPage = require('../pages/checkoutPage');
const RCloudPage = require('../pages/rcloudPage');
const MediaUtils = require('../utils/media-utils');
const Logger = require('../utils/logger');

/**
 * Service for Stripe checkout page verification
 * Pattern: Reused from PRO 2.0 project structure
 */
class CheckoutService {
  /**
   * Verify Stripe checkout page details
   * @param {Object} checkoutData - Contains checkoutUrl and currency
   * @returns {Promise<Object>} - Result of the checkout verification
   */
  static async verifyCheckoutPage(checkoutData) {
    // Validate the checkout URL
    if (!checkoutData.checkoutUrl) {
      throw new Error('checkoutUrl is required in the checkoutData');
    }

    // Execute with browser setup and cleanup
    return await BaseService.execute(
      // The automation function to run
      async (browser, context, page, data) => {
        // Create CheckoutPage instance
        const checkoutPage = new CheckoutPage(context, page);

        // Navigate to Stripe checkout URL
        await checkoutPage.goto(data.checkoutUrl);

        // Wait for page to load
        await checkoutPage.waitForPageLoad();

        // Select currency if specified and toggle exists
        if (data.currency) {
          await checkoutPage.selectCurrency(data.currency);
        }

        // Take screenshot of the checkout page (after currency selection)
        const screenshotPath = await MediaUtils.takeScreenshot(
          page,
          'checkout_page',
          'verify'
        );

        // Get all checkout details
        const checkoutDetails = await checkoutPage.getAllCheckoutDetails();

        // Return data to be included in the result
        return {
          message: 'Checkout page verification completed',
          data: {
            checkoutUrl: data.checkoutUrl,
            currency: data.currency,
            screenshot: screenshotPath,
            checkoutDetails
          }
        };
      },
      // Pass the input data
      checkoutData,
      // Pass the operation name
      'verify_checkout'
    );
  }

  /**
   * Complete payment on Stripe checkout page using Card
   * @param {Object} paymentData - Contains checkoutUrl, card details, and optional currency
   * @returns {Promise<Object>} - Result of the payment process
   */
  static async payCheckoutWithCard(paymentData) {
    // Validate the checkout URL
    if (!paymentData.checkoutUrl) {
      throw new Error('checkoutUrl is required in the paymentData');
    }

    // Validate card details
    if (!paymentData.cardNumber || !paymentData.cardExpiry || 
        !paymentData.cardCvc || !paymentData.cardholderName) {
      throw new Error('All card details are required: cardNumber, cardExpiry, cardCvc, cardholderName');
    }

    // Execute with browser setup and cleanup
    return await BaseService.execute(
      // The automation function to run
      async (browser, context, page, data) => {
        // Set Local Storage for MLM domain (will be available when redirected back)
        if (data.authToken) {
          Logger.info('Setting Local Storage for MLM domain');
          
          // Log all values that will be set
          Logger.info('Local Storage items to be set:');
          Logger.info(`  - mlmWebToken = ${data.authToken}`);
          Logger.info(`  - mlmWebVersion = 4.1.0`);
          Logger.info(`  - mlmWebSelectedUnit = mlm2`);
          if (data.userData) {
            Logger.info(`  - mlmWebUser = ${JSON.stringify(data.userData)}`);
          }
          
          // Add Local Storage state to context for the MLM domain
          await context.addInitScript(({ authToken, userData }) => {
            // This script will run on every page load, but only set for mlm.rapsodo.com
            if (window.location.hostname.includes('mlm.rapsodo.com')) {
              localStorage.setItem('mlmWebToken', authToken);
              localStorage.setItem('mlmWebVersion', '4.1.0');
              localStorage.setItem('mlmWebSelectedUnit', 'mlm2');
              if (userData) {
                localStorage.setItem('mlmWebUser', JSON.stringify(userData));
              }
            }
          }, { authToken: data.authToken, userData: data.userData });
          
          const itemCount = data.userData ? 4 : 3;
          Logger.info(`Local Storage init script added (${itemCount} items will be set when MLM domain loads)`);
        }
        
        // Create CheckoutPage instance
        const checkoutPage = new CheckoutPage(context, page);

        // Navigate to Stripe checkout URL
        await checkoutPage.goto(data.checkoutUrl);

        // Wait for page to load
        await checkoutPage.waitForPageLoad();

        // Select currency if specified and toggle exists
        if (data.currency) {
          await checkoutPage.selectCurrency(data.currency);
        }

        // Take screenshot before payment
        const beforeScreenshot = await MediaUtils.takeScreenshot(
          page,
          'checkout_before_payment',
          'pay'
        );

        // Complete card payment
        await checkoutPage.completeCardPayment({
          cardNumber: data.cardNumber,
          cardExpiry: data.cardExpiry,
          cardCvc: data.cardCvc,
          cardholderName: data.cardholderName
        });

        // Wait for redirect to success or cancel URL (timeout: 60 seconds)
        // Use provided URLs or defaults
        const successUrl = data.successUrl || 'https://test.mlm.rapsodo.com/mlm-web/profile/membership?success';
        const cancelUrl = data.cancelUrl || 'https://test.mlm.rapsodo.com/mlm-web';
        
        let paymentSucceeded = false;
        
        Logger.info(`Waiting for redirect to success or cancel URL (timeout: 60s)`);
        Logger.info(`  - Success URL pattern: ${successUrl}`);
        Logger.info(`  - Cancel URL pattern: ${cancelUrl}`);
        
        try {
          // Wait for URL to change to either success or cancel
          await page.waitForURL(url => {
            const currentUrl = url.toString();
            Logger.debug(`Checking URL: ${currentUrl}`);
            
            // Check if it's the success URL
            if (currentUrl.includes('membership?success') || currentUrl.includes(successUrl)) {
              Logger.info(`Success URL detected: ${currentUrl}`);
              return true;
            }
            
            // Check if it's the cancel URL (but not checkout URL)
            if (currentUrl.startsWith(cancelUrl) && !currentUrl.includes('checkout.stripe.com')) {
              Logger.info(`Cancel URL detected: ${currentUrl}`);
              return true;
            }
            
            return false;
          }, { timeout: 60000 });
          
          // Check which URL we landed on
          const finalUrl = page.url();
          paymentSucceeded = finalUrl.includes('membership?success');
          Logger.info(`Redirect completed - Payment ${paymentSucceeded ? 'SUCCEEDED' : 'FAILED'}`);
          
          // If payment succeeded and we're on the membership page, close welcome popup
          if (paymentSucceeded) {
            const rcloudPage = new RCloudPage(context, page);
            await rcloudPage.closeWelcomePopup();
          }
          
        } catch (error) {
          // Timeout - no redirect occurred
          const currentUrl = page.url();
          Logger.warn(`Redirect timeout after 60s. Current URL: ${currentUrl}`);
          
          // Check if we're still on checkout page or somehow reached success/cancel
          paymentSucceeded = currentUrl.includes('membership?success');
        }

        // Take screenshot after payment processing (after closing popup)
        const afterScreenshot = await MediaUtils.takeScreenshot(
          page,
          paymentSucceeded ? 'checkout_payment_success' : 'checkout_payment_failed',
          'pay'
        );

        // Get final URL
        const finalUrl = page.url();

        // Return data to be included in the result
        return {
          message: paymentSucceeded ? 'Payment completed successfully' : 'Payment was not successful',
          data: {
            checkoutUrl: data.checkoutUrl,
            currency: data.currency,
            paymentSucceeded: paymentSucceeded,
            finalUrl: finalUrl,
            expectedSuccessUrl: successUrl,
            expectedCancelUrl: cancelUrl,
            beforeScreenshot: beforeScreenshot,
            afterScreenshot: afterScreenshot
          }
        };
      },
      // Pass the input data
      paymentData,
      // Pass the operation name
      'pay_checkout_card'
    );
  }
}

module.exports = CheckoutService;

