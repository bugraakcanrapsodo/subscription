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
      
      // Payment method options
      cardOption: '[data-testid="card-accordion-item-button"]',
      cashAppPayOption: '[data-testid="cashapp-accordion-item-button"]',
      bankOption: '[data-testid="link_instant_debit-accordion-item-button"]',
      
      // Card payment form
      cardNumber: '#cardNumber',
      cardExpiry: '#cardExpiry',
      cardCvc: '#cardCvc',
      cardholderName: '#billingName',
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
      await this.page.locator(selector).click();
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
    // Use BasePage click method (which has fallback to JavaScript click)
    await this.click(this.selectors.cardOption);
    Logger.info('Card accordion button clicked');
    
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
    await this.page.waitForTimeout(500);
    
    Logger.info('All card details filled successfully');
  }

  /**
   * Click the Pay/Start Trial button
   * @returns {Promise<void>}
   */
  async clickPayButton() {
    Logger.info('Clicking Pay/Start Trial button');
    await this.page.locator(this.selectors.payButton).click();
    Logger.info('Pay button clicked');
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
    
    await this.page.waitForTimeout(500);

    // Click pay button
    await this.clickPayButton();
    
    Logger.info('Card payment flow completed');
  }
}

module.exports = CheckoutPage;

