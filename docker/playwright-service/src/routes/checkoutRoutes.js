const express = require('express');
const router = express.Router();
const CheckoutService = require('../services/checkout-service');
const Logger = require('../utils/logger');
const mullvadVPN = require('../services/mullvad-cli-manager');
const fs = require('fs');
const path = require('path');

// Load valid countries from locations.json (from root config directory)
let validCountries = null;
let countryNames = {};

function loadValidCountries() {
  if (validCountries) return validCountries;
  
  try {
    // Use locations.json from root config directory (single source of truth)
    const locationsPath = path.join(__dirname, '../../../../config/locations.json');
    const locationsData = JSON.parse(fs.readFileSync(locationsPath, 'utf8'));
    
    validCountries = Object.keys(locationsData.locations);
    
    // Build country name mapping for helpful error messages
    validCountries.forEach(code => {
      countryNames[code] = locationsData.locations[code].name;
    });
    
    Logger.info(`Loaded ${validCountries.length} valid VPN countries from locations.json`);
    return validCountries;
  } catch (error) {
    Logger.error(`Failed to load locations.json: ${error.message}`);
    // Fallback to basic list
    validCountries = ['us', 'ca', 'au', 'gb', 'jp', 'sg', 'de', 'fr', 'es', 'it', 'nl', 'be', 'at', 'ie', 'pt', 'fi', 'gr'];
    return validCountries;
  }
}

function validateCountry(country) {
  const valid = loadValidCountries();
  
  if (!country) {
    return { valid: true, message: 'No country specified, will use default' };
  }
  
  const countryLower = country.toLowerCase();
  
  if (!valid.includes(countryLower)) {
    const availableList = valid.map(c => `${c} (${countryNames[c] || c.toUpperCase()})`).join(', ');
    return {
      valid: false,
      message: `Invalid country code '${country}'. Valid countries are: ${availableList}`
    };
  }
  
  return { valid: true, country: countryLower };
}

/**
 * Verify Stripe checkout page details
 * POST /api/checkout/verify
 * Body: { 
 *   "checkoutUrl": "https://checkout.stripe.com/...",
 *   "currency": "US" (optional, default: "US"),
 *   "country": "us" (optional, VPN country code: us, ca, au, gb, de, fr, es, jp, sg)
 * }
 */
router.post('/verify', async (req, res) => {
  try {
    const { checkoutUrl, currency = 'US', country } = req.body;

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

    // Validate country if provided
    if (country) {
      const validation = validateCountry(country);
      if (!validation.valid) {
        return res.status(400).json({
          success: false,
          error: 'Invalid country code',
          message: validation.message,
          providedCountry: country
        });
      }
    }

    // Connect to VPN if country is provided
    let vpnConnected = false;
    let vpnLocationVerification = null;
    if (country) {
      try {
        Logger.info(`Connecting to VPN country: ${country}`);
        const connectResult = await mullvadVPN.connect(country);
        vpnConnected = true;
        vpnLocationVerification = connectResult.verification;
        
        // Wait 5 seconds after VPN connection for network stack and DNS to settle
        // This prevents browser crashes (SIGSEGV) and DNS resolution failures (ERR_NAME_NOT_RESOLVED)
        Logger.info('Waiting 5 seconds for VPN network and DNS to settle...');
        await new Promise(resolve => setTimeout(resolve, 5000));
      } catch (error) {
        Logger.error(`VPN connection failed: ${error.message}`);
        return res.status(500).json({
          success: false,
          error: 'Failed to connect to VPN',
          message: error.message,
          country: country
        });
      }
    }

    try {
      // Prepare checkout data
      const checkoutData = {
        checkoutUrl: checkoutUrl.trim(),
        currency: currency ? currency.toUpperCase() : 'US',
        country: country
      };

      // Call the checkout service to handle the automation
      const result = await CheckoutService.verifyCheckoutPage(checkoutData);

      // Add VPN location verification to response
      if (vpnLocationVerification) {
        result.vpnLocationVerification = vpnLocationVerification;
      }

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
    } finally {
      // Disconnect VPN if it was connected
      if (vpnConnected) {
        try {
          Logger.info('Disconnecting VPN...');
          await mullvadVPN.disconnect();
        } catch (error) {
          Logger.warn(`VPN disconnect warning: ${error.message}`);
        }
      }
    }
  } catch (error) {
    Logger.error(`Error in verify route: ${error.message}`);
    return res.status(500).json({
      success: false,
      error: 'Request failed',
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
 *   "country": "us" (optional, VPN country code: us, ca, au, gb, de, fr, es, jp, sg),
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
      country,
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

    // Validate country if provided
    if (country) {
      const validation = validateCountry(country);
      if (!validation.valid) {
        return res.status(400).json({
          success: false,
          error: 'Invalid country code',
          message: validation.message,
          providedCountry: country
        });
      }
    }

    // Connect to VPN if country is provided
    let vpnConnected = false;
    let vpnLocationVerification = null;
    if (country) {
      try {
        Logger.info(`Connecting to VPN country: ${country}`);
        const connectResult = await mullvadVPN.connect(country);
        vpnConnected = true;
        vpnLocationVerification = connectResult.verification;
        
        // Wait 5 seconds after VPN connection for network stack and DNS to settle
        // This prevents browser crashes (SIGSEGV) and DNS resolution failures (ERR_NAME_NOT_RESOLVED)
        Logger.info('Waiting 5 seconds for VPN network and DNS to settle...');
        await new Promise(resolve => setTimeout(resolve, 5000));
      } catch (error) {
        Logger.error(`VPN connection failed: ${error.message}`);
        return res.status(500).json({
          success: false,
          error: 'Failed to connect to VPN',
          message: error.message,
          country: country
        });
      }
    }

    try {
      // Prepare payment data
      const paymentData = {
        checkoutUrl: checkoutUrl.trim(),
        cardNumber: cardNumber.trim(),
        cardExpiry: cardExpiry.trim(),
        cardCvc: cardCvc.trim(),
        cardholderName: cardholderName.trim(),
        currency: currency ? currency.toUpperCase() : 'US',
        country: country
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

      // Add VPN location verification to response
      if (vpnLocationVerification) {
        result.vpnLocationVerification = vpnLocationVerification;
      }

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
    } finally {
      // Disconnect VPN if it was connected
      if (vpnConnected) {
        try {
          Logger.info('Disconnecting VPN...');
          await mullvadVPN.disconnect();
        } catch (error) {
          Logger.warn(`VPN disconnect warning: ${error.message}`);
        }
      }
    }
  } catch (error) {
    Logger.error(`Error in pay-card route: ${error.message}`);
    return res.status(500).json({
      success: false,
      error: 'Request failed',
      message: error.message
    });
  }
});

module.exports = router;

