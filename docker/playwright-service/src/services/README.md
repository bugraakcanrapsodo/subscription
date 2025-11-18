# Services Directory

This directory contains automation services following the PRO 2.0 BaseService pattern.

## BaseService Pattern (from PRO 2.0)

All automation services should use `BaseService.execute()` which provides:
- ✅ Automatic browser initialization and cleanup
- ✅ Automatic video recording with timestamped filenames
- ✅ Error handling with error videos for debugging
- ✅ Consistent response structure
- ✅ Debug mode support

## Creating a New Service

### 1. Create Service File

Example: `stripeCheckoutService.js`

```javascript
const BaseService = require('./base-service');
const BasePage = require('../pages/basePage');
const MediaUtils = require('../utils/media-utils');

class StripeCheckoutService {
  /**
   * Complete Stripe checkout flow
   * @param {Object} checkoutData - { email, cardNumber, expiry, cvc, ... }
   * @returns {Promise<Object>} - Result with success status
   */
  static async completeCheckout(checkoutData) {
    // Define the automation function
    const checkoutAutomation = async (browser, context, page, data) => {
      const basePage = new BasePage(context, page);
      
      // Your automation logic here
      await basePage.goto('https://checkout.stripe.com/...');
      await basePage.enter('#email', data.email);
      await basePage.enter('#cardNumber', data.cardNumber);
      // ... more automation steps
      
      // Take screenshots at key points
      const screenshot = await MediaUtils.takeScreenshot(
        page,
        'checkout',
        'complete'
      );
      
      // Return result
      return {
        message: 'Checkout completed successfully',
        data: {
          email: data.email,
          screenshot
        }
      };
    };

    // Execute with BaseService (handles everything automatically)
    return await BaseService.execute(
      checkoutAutomation,
      checkoutData,
      'stripe_checkout'  // This becomes the video filename: YYYY-MM-DD_HH-MM-SS_stripe_checkout.webm
    );
  }
}

module.exports = StripeCheckoutService;
```

### 2. Create Route

Example: `checkoutRoutes.js`

```javascript
const express = require('express');
const router = express.Router();
const StripeCheckoutService = require('../services/stripeCheckoutService');

router.post('/complete', async (req, res) => {
  const { email, cardNumber, expiry, cvc } = req.body;
  
  // Validation
  if (!email || !cardNumber) {
    return res.status(400).json({
      success: false,
      error: 'Missing required fields'
    });
  }
  
  // Call service
  const result = await StripeCheckoutService.completeCheckout({
    email,
    cardNumber,
    expiry,
    cvc
  });
  
  // Return response
  const statusCode = result.success ? 200 : 500;
  res.status(statusCode).json(result);
});

module.exports = router;
```

### 3. Register Route

In `routes/index.js`:

```javascript
const checkoutRoutes = require('./checkoutRoutes');
router.use('/checkout', checkoutRoutes);
```

## Benefits of This Pattern

1. **Consistent**: All services follow the same structure
2. **Clean**: No manual browser lifecycle management
3. **Debuggable**: Videos automatically saved with descriptive names
4. **Error Handling**: Errors captured with videos for debugging
5. **Maintainable**: Easy to understand and modify

## Video Naming

Videos are automatically named: `YYYY-MM-DD_HH-MM-SS_<operation>.webm`

Examples:
- `2025-11-18_17-16-45_stripe_checkout.webm`
- `2025-11-18_17-20-30_error_stripe_checkout.webm` (if error occurs)

## Response Structure

Success:
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { ... }
}
```

Error:
```json
{
  "success": false,
  "message": "Error message here"
}
```

Note: Videos are recorded for debugging but not included in API responses (following PRO 2.0 pattern).
