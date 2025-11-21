const express = require('express');
const router = express.Router();
const CheckoutService = require('../services/checkout-service');
const Logger = require('../utils/logger');

/**
 * Verify Stripe checkout page details
 * POST /api/checkout/verify
 * Body: { 
 *   "checkoutUrl": "https://checkout.stripe.com/...",
 *   "currency": "US" (optional, default: "US")
 * }
 */
router.post('/verify', async (req, res) => {
  try {
    const { checkoutUrl, currency = 'US' } = req.body;

    // Validate required field
    if (!checkoutUrl) {
      return res.status(400).json({
        success: false,
        error: 'Missing required field: checkoutUrl'
      });
    }

    // Validate checkoutUrl format
    if (typeof checkoutUrl !== 'string' || !checkoutUrl.trim()) {
      return res.status(400).json({
        success: false,
        error: 'Invalid checkoutUrl. Must be a non-empty string.'
      });
    }

    // Validate checkoutUrl is from Stripe
    if (!checkoutUrl.includes('checkout.stripe.com')) {
      return res.status(400).json({
        success: false,
        error: 'Invalid checkoutUrl. Must be a Stripe checkout URL (checkout.stripe.com).',
        providedUrl: checkoutUrl
      });
    }


    Logger.info(`Processing checkout verification for URL: ${checkoutUrl.substring(0, 80)}...`);

    // Prepare checkout data
    const checkoutData = {
      checkoutUrl: checkoutUrl.trim(),
      currency: currency ? currency.toUpperCase() : 'US'
    };

    // Call the checkout service to handle the automation
    const result = await CheckoutService.verifyCheckoutPage(checkoutData);

    // Return response based on result
    if (result.success) {
      return res.status(200).json(result);
    } else {
      return res.status(500).json(result);
    }
  } catch (error) {
    Logger.error(`Error verifying checkout page: ${error.message}`);
    return res.status(500).json({
      success: false,
      error: 'Failed to verify checkout page',
      message: error.message
    });
  }
});

/**
 * Complete payment on Stripe checkout page using Card
 * POST /api/checkout/pay-card
 * Body: { 
 *   "checkoutUrl": "https://checkout.stripe.com/..." (required),
 *   "cardNumber": "4242424242424242" (required),
 *   "cardExpiry": "12/25" (required),
 *   "cardCvc": "123" (required),
 *   "cardholderName": "Test User" (required),
 *   "authToken": "jwt_token..." (required, auth token to set as mlmWebToken cookie),
 *   "userData": {...} (optional, user data from login response to set as mlmWebUser cookie),
 *   "currency": "US" (optional, default: "US"),
 *   "successUrl": "https://..." (optional, custom success redirect URL),
 *   "cancelUrl": "https://..." (optional, custom cancel redirect URL)
 * }
 */
router.post('/pay-card', async (req, res) => {
  try {
    const { 
      checkoutUrl, 
      cardNumber, 
      cardExpiry, 
      cardCvc, 
      cardholderName,
      currency = 'US',
      successUrl,
      cancelUrl,
      authToken,
      userData
    } = req.body;

    // Validate required fields
    const requiredFields = {
      checkoutUrl,
      cardNumber,
      cardExpiry,
      cardCvc,
      cardholderName,
      authToken
    };

    const missingFields = Object.entries(requiredFields)
      .filter(([_, value]) => !value)
      .map(([key]) => key);

    if (missingFields.length > 0) {
      return res.status(400).json({
        success: false,
        error: `Missing required fields: ${missingFields.join(', ')}`
      });
    }

    // Validate checkoutUrl format
    if (typeof checkoutUrl !== 'string' || !checkoutUrl.trim()) {
      return res.status(400).json({
        success: false,
        error: 'Invalid checkoutUrl. Must be a non-empty string.'
      });
    }

    // Validate checkoutUrl is from Stripe
    if (!checkoutUrl.includes('checkout.stripe.com')) {
      return res.status(400).json({
        success: false,
        error: 'Invalid checkoutUrl. Must be a Stripe checkout URL (checkout.stripe.com).',
        providedUrl: checkoutUrl
      });
    }

    // Validate card number format (basic check: only digits and spaces, 13-19 characters)
    const cardNumberClean = cardNumber.replace(/\s/g, '');
    if (!/^\d{13,19}$/.test(cardNumberClean)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid card number. Must be 13-19 digits.',
        field: 'cardNumber'
      });
    }

    // Validate expiry format (MM/YY or MMYY)
    if (!/^(0[1-9]|1[0-2])[\s\/]?\d{2}$/.test(cardExpiry.replace(/\s/g, ''))) {
      return res.status(400).json({
        success: false,
        error: 'Invalid expiry date. Must be in MM/YY format (e.g., 12/25).',
        field: 'cardExpiry'
      });
    }

    // Validate CVC format (3-4 digits)
    if (!/^\d{3,4}$/.test(cardCvc)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid CVC. Must be 3-4 digits.',
        field: 'cardCvc'
      });
    }

    // Validate cardholder name (must contain at least 1 character)
    if (cardholderName.trim().length < 1) {
      return res.status(400).json({
        success: false,
        error: 'Invalid cardholder name. Must be at least 1 character.',
        field: 'cardholderName'
      });
    }

    // Validate optional URLs if provided
    if (successUrl && (typeof successUrl !== 'string' || !successUrl.trim())) {
      return res.status(400).json({
        success: false,
        error: 'Invalid successUrl. Must be a non-empty string.',
        field: 'successUrl'
      });
    }

    if (cancelUrl && (typeof cancelUrl !== 'string' || !cancelUrl.trim())) {
      return res.status(400).json({
        success: false,
        error: 'Invalid cancelUrl. Must be a non-empty string.',
        field: 'cancelUrl'
      });
    }

    Logger.info(`Processing payment for checkout URL: ${checkoutUrl.substring(0, 80)}...`);

    // Prepare payment data
    const paymentData = {
      checkoutUrl: checkoutUrl.trim(),
      cardNumber: cardNumber.trim(),
      cardExpiry: cardExpiry.trim(),
      cardCvc: cardCvc.trim(),
      cardholderName: cardholderName.trim(),
      currency: currency ? currency.toUpperCase() : 'US'
    };

    // Add optional URLs if provided
    if (successUrl) {
      paymentData.successUrl = successUrl.trim();
    }
    if (cancelUrl) {
      paymentData.cancelUrl = cancelUrl.trim();
    }
    
    // Add required auth token for authenticated success page
    paymentData.authToken = authToken.trim();
    Logger.info('Auth token provided for authenticated success page');
    
    // Add optional user data for mlmWebUser cookie
    if (userData) {
      paymentData.userData = userData;
      Logger.info('User data provided for mlmWebUser cookie');
    }

    // Call the checkout service to handle the automation
    const result = await CheckoutService.payCheckoutWithCard(paymentData);

    // Return response based on result
    if (result.success) {
      return res.status(200).json(result);
    } else {
      return res.status(500).json(result);
    }
  } catch (error) {
    Logger.error(`Error processing payment: ${error.message}`);
    return res.status(500).json({
      success: false,
      error: 'Failed to process payment',
      message: error.message
    });
  }
});

module.exports = router;

