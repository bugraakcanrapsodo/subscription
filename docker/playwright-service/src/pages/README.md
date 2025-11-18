# Pages Directory

## TODO: Implement Stripe Checkout Page Objects

This directory should contain page object classes for Stripe checkout automation.

### Required Pages:

#### 1. `stripeCheckoutPage.js`
Page object for Stripe checkout form interactions:
- Email input
- Card number input (iframe handling)
- Expiry date input (iframe)
- CVC input (iframe)
- Billing details
- Submit button
- Error messages
- Success indicators

#### 2. `basePage.js` (Optional)
Common page object functionality:
- Wait helpers
- Element interaction helpers
- Screenshot helpers
- Error handling

### Example Structure:

```javascript
class StripeCheckoutPage {
  constructor(page) {
    this.page = page;
  }

  async fillEmail(email) {
    // TODO: Implement
  }

  async fillCardDetails(cardNumber, expiry, cvc) {
    // TODO: Handle Stripe iframe
    // TODO: Implement card input
  }

  async fillBillingDetails(name, country, zip) {
    // TODO: Implement
  }

  async submit() {
    // TODO: Implement
  }

  async waitForSuccess() {
    // TODO: Implement
  }

  async getErrorMessage() {
    // TODO: Implement
  }
}
```

### Note:
Stripe checkout uses iframes for card inputs - special handling required!

