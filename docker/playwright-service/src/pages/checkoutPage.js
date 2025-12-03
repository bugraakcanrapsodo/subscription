const BasePage = require('./basePage');
const Logger = require('../utils/logger');

/**
 * Stripe Checkout Page - Page Object Model
 * Handles Stripe checkout page interactions and element verification
 */
class CheckoutPage extends BasePage {
  constructor(context, page) {
    super(context, page);
    
    // Selectors
    this.selectors = {
      // Product summary section
      productSummaryName: '[data-testid="product-summary-name"]',
      productSummaryTotalAmount: '[data-testid="product-summary-total-amount"]',
      
      // Line item details
      lineItemProductName: '[data-testid="line-item-product-name"]',
      lineItemTotalAmount: '[data-testid="line-item-total-amount"]',
      
      // Order details footer
      subtotalAmount: '[data-testid="order-details-footer-subtotal-amount"]',
      totalAmount: '#OrderDetails-TotalAmount',
      trialAmount: '#OrderDetails-TrialAmount',
      
      // Currency toggle
      currencyToggle: '[data-testid="equal-presentment-currency-toggle-toggles"]',
      currencyButtonTemplate: 'button img[alt="{}"]',
      
      // Payment method options (multiple possible selectors due to Stripe UI variations)
      cardOption: '[data-testid="card-accordion-item-button"]',
      cardOptionRadioButton: '#payment-method-accordion-item-title-card',  // Alternative selector (radio input)
      cashAppPayOption: '[data-testid="cashapp-accordion-item-button"]',
      bankOption: '[data-testid="link_instant_debit-accordion-item-button"]',
      
      // Card payment form
      cardNumber: '#cardNumber',
      cardExpiry: '#cardExpiry',
      cardCvc: '#cardCvc',
      cardholderName: '#billingName',
      
      // Billing address fields (appear dynamically per country)
      billingAddressLine1: '#billingAddressLine1',
      billingAddressLine2: '#billingAddressLine2',
      billingCity: '#billingLocality',
      billingZip: '#billingPostalCode',
      billingState: '#billingAdministrativeArea',
      
      // Stripe Pass checkbox (makes phone mandatory if checked)
      stripePassCheckbox: '#enableStripePass',
      billingPhone: '#billingPhone',
      
      payButton: '[data-testid="hosted-payment-submit-button"]'
    };
  }

  /**
   * Get product summary name (e.g., "Try MLM2PRO Premium Membership")
   * @returns {Promise<string>} Product summary name text
   */
  async getProductSummaryName() {
    Logger.info('Getting product summary name');
    return await this.getText(this.selectors.productSummaryName);
  }

  /**
   * Get product summary total amount (e.g., "45 days free")
   * @returns {Promise<string>} Product summary total amount text
   */
  async getProductSummaryTotalAmount() {
    Logger.info('Getting product summary total amount');
    return await this.getText(this.selectors.productSummaryTotalAmount);
  }

  /**
   * Get line item product name (e.g., "MLM2PRO Premium Membership")
   * @returns {Promise<string>} Line item product name text
   */
  async getLineItemProductName() {
    Logger.info('Getting line item product name');
    return await this.getText(this.selectors.lineItemProductName);
  }

  /**
   * Get line item total amount (e.g., "45 days free")
   * @returns {Promise<string>} Line item total amount text
   */
  async getLineItemTotalAmount() {
    Logger.info('Getting line item total amount');
    return await this.getText(this.selectors.lineItemTotalAmount);
  }

  /**
   * Get subtotal amount (e.g., "$199.99")
   * @returns {Promise<string>} Subtotal amount text
   */
  async getSubtotalAmount() {
    Logger.info('Getting subtotal amount');
    return await this.getText(this.selectors.subtotalAmount);
  }

  /**
   * Get total amount after trial (e.g., "$199.99")
   * @returns {Promise<string>} Total amount text
   */
  async getTotalAmount() {
    Logger.info('Getting total amount');
    return await this.getText(this.selectors.totalAmount);
  }

  /**
   * Get trial amount due today (e.g., "$0.00")
   * @returns {Promise<string>} Trial amount text
   */
  async getTrialAmount() {
    Logger.info('Getting trial amount');
    return await this.getText(this.selectors.trialAmount);
  }

  /**
   * Get all checkout page details at once
   * @returns {Promise<Object>} Object containing all checkout details
   */
  async getAllCheckoutDetails() {
    Logger.info('Getting all checkout details');
    
    // Try to get all fields, return null if they don't exist
    const details = {
      productSummaryName: await this.getTextOrNull(this.selectors.productSummaryName),
      productSummaryTotalAmount: await this.getTextOrNull(this.selectors.productSummaryTotalAmount),
      lineItemProductName: await this.getTextOrNull(this.selectors.lineItemProductName),
      lineItemTotalAmount: await this.getTextOrNull(this.selectors.lineItemTotalAmount),
      subtotalAmount: await this.getTextOrNull(this.selectors.subtotalAmount),
      totalAmount: await this.getTextOrNull(this.selectors.totalAmount),
      trialAmount: await this.getTextOrNull(this.selectors.trialAmount)
    };
    
    Logger.info('All checkout details retrieved successfully');
    return details;
  }

  /**
   * Check if currency toggle exists on the page
   * @returns {Promise<boolean>}
   */
  async hasCurrencyToggle() {
    try {
      await this.page.waitForSelector(this.selectors.currencyToggle, { timeout: 2000 });
      Logger.info('Currency toggle detected');
      return true;
    } catch (e) {
      Logger.info('No currency toggle found');
      return false;
    }
  }

  /**
   * Select currency if toggle exists
   * @param {string} currency - Currency code (e.g., "US", "TR")
   * @returns {Promise<void>}
   */
  async selectCurrency(currency) {
    Logger.info(`Attempting to select currency: ${currency}`);
    
    const hasCurrency = await this.hasCurrencyToggle();
    if (!hasCurrency) {
      Logger.info('No currency toggle available, skipping currency selection');
      return;
    }

    try {
      // Click the currency button using template selector
      const selector = this.getOptionSelector(this.selectors.currencyButtonTemplate, currency);
      await this.click(selector);
      Logger.info(`Currency ${currency} selected successfully`);
      
      // Wait for page to update after currency selection
      await this.page.waitForTimeout(1000);
    } catch (error) {
      Logger.warn(`Failed to select currency ${currency}: ${error.message}`);
    }
  }

  /**
   * Wait for checkout page to load completely
   * @returns {Promise<void>}
   */
  async waitForPageLoad() {
    Logger.info('Waiting for checkout page to load');
    
    // Wait for total amount which exists on all checkout pages
    await this.page.waitForSelector(this.selectors.totalAmount, { timeout: 30000 });
    
    // Wait for page to stabilize
    await this.page.waitForTimeout(2000);
    Logger.info('Checkout page loaded successfully');
  }
  
  /**
   * Check if this is a trial checkout page (has trial amount field)
   * @returns {Promise<boolean>}
   */
  async isTrialCheckout() {
    try {
      await this.page.waitForSelector(this.selectors.trialAmount, { timeout: 2000 });
      return true;
    } catch (e) {
      return false;
    }
  }

  /**
   * Select card payment option
   * @returns {Promise<void>}
   */
  async selectCardPayment() {
    try {
      Logger.info('Looking for card accordion button...');
      
      // Check if radio button is visible (newer Stripe UI)
      const isRadioButtonVisible = await this.isVisible(this.selectors.cardOptionRadioButton, 2000);
      
      if (isRadioButtonVisible) {
        Logger.info('Radio button visible - clicking cardOption selector (not visible but clickable)');
        // Radio button is visible but not clickable
        // Click cardOption instead (not visible but clickable via JS)
        await this.click(this.selectors.cardOption);
        Logger.info('Card accordion button clicked via cardOption selector');
      } else {
        // Radio button not visible - card form is already open
        Logger.info('Radio button not visible - card form is already open');
      }
      
    } catch (error) {
      Logger.info('Error checking card accordion button - card form might already be open');
    }
    
    // Wait for card form to appear
    await this.page.waitForSelector(this.selectors.cardNumber, { timeout: 10000, state: 'visible' });
    Logger.info('Card payment form is now visible');
  }

  /**
   * Fill card payment details
   * @param {Object} cardDetails - Card information
   * @param {string} cardDetails.cardNumber - Card number
   * @param {string} cardDetails.cardExpiry - Expiry date (MM/YY format)
   * @param {string} cardDetails.cardCvc - CVC code
   * @param {string} cardDetails.cardholderName - Name on card
   * @param {string} cardDetails.country - Country code (us, ca, gb, etc.)
   * @returns {Promise<void>}
   */
  async fillCardDetails(cardDetails) {
    Logger.info('Filling card payment details');
    
    // Fill card number
    await this.enter(this.selectors.cardNumber, cardDetails.cardNumber);
    Logger.info('Card number entered');
    await this.page.waitForTimeout(500);
    
    // Fill expiry date
    await this.enter(this.selectors.cardExpiry, cardDetails.cardExpiry);
    Logger.info('Expiry date entered');
    await this.page.waitForTimeout(500);
    
    // Fill CVC
    await this.enter(this.selectors.cardCvc, cardDetails.cardCvc);
    Logger.info('CVC entered');
    await this.page.waitForTimeout(500);
    
    // Fill cardholder name
    await this.enter(this.selectors.cardholderName, cardDetails.cardholderName);
    Logger.info('Cardholder name entered');
    await this.page.waitForTimeout(1000); // Wait for address fields to appear dynamically
    
    // Fill billing address based on country requirements
    const country = (cardDetails.country || 'us').toLowerCase();
    await this.fillBillingAddress(country);
    
    // UNCHECK "Save my information for faster checkout" if it's checked - it makes phone mandatory
    try {
      const stripePassCheckbox = this.page.locator(this.selectors.stripePassCheckbox);
      const isChecked = await stripePassCheckbox.isChecked({ timeout: 2000 });
      
      if (isChecked) {
        Logger.info('Stripe Pass checkbox is checked by default, unchecking it...');
        await stripePassCheckbox.uncheck();
        Logger.info('✓ Stripe Pass checkbox unchecked to avoid phone requirement');
        await this.page.waitForTimeout(500);
      } else {
        Logger.info('Stripe Pass checkbox is not checked, no action needed');
      }
    } catch (error) {
      Logger.info('Stripe Pass checkbox not found or not visible, continuing...');
    }
    
    Logger.info('All card details filled successfully');
  }
  
  /**
   * Fill billing address based on country requirements
   * @param {string} country - Country code (us, ca, gb, etc.)
   * @returns {Promise<void>}
   */
  async fillBillingAddress(country) {
    Logger.info(`Filling billing address for country: ${country.toUpperCase()}`);
    
    try {
      if (country === 'us') {
        // USA requires: address line 1, city, zip, state
        Logger.info('Filling US address fields');
        
        await this.enter(this.selectors.billingAddressLine1, '123 Test Street');
        Logger.info('Address line 1: 123 Test Street');
        
        // Wait 2 seconds for Google autocomplete dropdown to appear
        Logger.info('Waiting 2 seconds for Google autocomplete dropdown...');
        await this.page.waitForTimeout(2000);
        
        // Dismiss Google autocomplete dropdown by pressing Escape
        await this.page.keyboard.press('Escape');
        Logger.info('Dismissed Google autocomplete dropdown');
        await this.page.waitForTimeout(500);
        
        await this.enter(this.selectors.billingCity, 'New York');
        Logger.info('City: New York');
        await this.page.waitForTimeout(500);
        
        await this.enter(this.selectors.billingZip, '10001');
        Logger.info('ZIP: 10001');
        await this.page.waitForTimeout(500);
        
        // Select state from dropdown
        await this.page.locator(this.selectors.billingState).selectOption('NY');
        Logger.info('State: NY');
        
      } else if (country === 'ca') {
        // Canada requires only: postal code
        Logger.info('Filling Canadian postal code');
        
        await this.enter(this.selectors.billingZip, 'M5H 2N2');
        Logger.info('Postal code: M5H 2N2');
        
      } else if (country === 'gb') {
        // UK requires only: postal code
        Logger.info('Filling UK postal code');
        
        await this.enter(this.selectors.billingZip, 'SW1A 1AA');
        Logger.info('Postal code: SW1A 1AA');
        
      } else {
        // Other countries (de, fr, au, sg, jp) don't require address
        Logger.info(`Country ${country.toUpperCase()} does not require billing address, skipping`);
      }
      
      await this.page.waitForTimeout(500);
      
    } catch (error) {
      Logger.warn(`Error filling billing address for ${country}: ${error.message}`);
      Logger.info('Continuing with payment...');
    }
  }

  /**
   * Click the Pay/Start Trial button
   * @returns {Promise<void>}
   */
  async clickPayButton() {
    Logger.info('Clicking Pay/Start Trial button');
    await this.click(this.selectors.payButton);
  }

  /**
   * Complete card payment flow
   * @param {Object} cardDetails - Card information
   * @returns {Promise<void>}
   */
  async completeCardPayment(cardDetails) {
    Logger.info('Starting complete card payment flow');
    
    // Select card payment option
    await this.selectCardPayment();

    await this.page.waitForTimeout(500);
    
    // Fill card details
    await this.fillCardDetails(cardDetails);
    
    await this.page.waitForTimeout(1000);

    // Click pay button
    await this.clickPayButton();
    
    Logger.info('Card payment flow completed');
  }
}

module.exports = CheckoutPage;

