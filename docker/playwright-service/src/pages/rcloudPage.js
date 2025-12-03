const BasePage = require('./basePage');
const Logger = require('../utils/logger');

/**
 * Page Object for RCloud Membership page
 * URL: https://test.mlm.rapsodo.com/mlm-web/profile/membership
 */
class RCloudPage extends BasePage {
  constructor(context, page) {
    super(context, page);

    // Selectors
    this.selectors = {
      // Navigation
      profileMenuItem: '#menu-item-content-Profile',

      // Welcome Popup
      closeButton: '#close-button',

      // Active subscription info
      activeSubscriptionMembership: '#active-subscription-membership', // Fallback: Contains "Membership: " prefix
      activeSubscriptionType: '#active-subscription-membership-type', // Preferred: No prefix
      activeSubscriptionExpireDate: '#active-subscription-expire-date',

      // Subscription cards
      subscriptionCardName: '.subscription-card-name',
      subscriptionCardPriceValue: '#subscription-card-price-value'
    };
  }

  /**
   * Close welcome popup if it exists
   * This popup appears after successful payment
   */
  async closeWelcomePopup() {
    try {
      Logger.info('Checking for welcome popup...');
      // Wait for close button with a short timeout
      await this.page.waitForSelector(this.selectors.closeButton, { timeout: 5000 });
      Logger.info('Welcome popup found, closing...');
      await this.click(this.selectors.closeButton);
      await this.page.waitForTimeout(1000); // Wait for popup to close
      Logger.info('Welcome popup closed');
    } catch (error) {
      Logger.info('No welcome popup found or already closed');
    }
  }

  /**
   * Navigate to Profile > Membership page
   */
  async navigateToMembershipPage() {
    Logger.info('Navigating to RCloud membership page');

    // Go to main web app
    await this.goto('https://test.mlm.rapsodo.com/mlm-web/');
    await this.page.waitForLoadState('domcontentloaded');

    // Click Profile menu item
    Logger.info('Clicking Profile menu item');
    await this.click(this.selectors.profileMenuItem);

    // Wait for membership page to load
    await this.page.waitForLoadState('domcontentloaded');
    Logger.info('Membership page loaded');
  }

  /**
   * Get active subscription membership type
   * Tries to get from span first, falls back to div if span doesn't exist
   * @returns {Promise<string>}
   */
  async getActiveSubscriptionType() {
    try {
      // Try to get from span (preferred - no prefix)
      await this.page.waitForSelector(this.selectors.activeSubscriptionType, { timeout: 2000 });
      const membershipType = await this.getText(this.selectors.activeSubscriptionType);
      Logger.info(`Got membership type from span: ${membershipType}`);
      return membershipType;
    } catch (error) {
      // Fallback to div (returns with "Membership: " prefix as is)
      Logger.info('Span not found, falling back to div element');
      try {
        const membershipText = await this.getText(this.selectors.activeSubscriptionMembership);
        Logger.info(`Got membership type from div: ${membershipText}`);
        return membershipText;
      } catch (divError) {
        Logger.warn('Neither span nor div element found for membership type');
        return "";
      }
    }
  }

  /**
   * Get active subscription expire date
   * Returns empty string if no active subscription
   * @returns {Promise<string>}
   */
  async getActiveSubscriptionExpireDate() {
    try {
      await this.page.waitForSelector(this.selectors.activeSubscriptionExpireDate, { timeout: 2000 });
      const expireDate = await this.getText(this.selectors.activeSubscriptionExpireDate);
      Logger.info(`Got expire date: ${expireDate}`);
      return expireDate;
    } catch (error) {
      Logger.info('Expire date element not found (no active subscription)');
      return "";
    }
  }

  /**
   * Get all subscription card offers
   * @returns {Promise<Array<{name: string, price: string}>>}
   */
  async getSubscriptionCards() {
    Logger.info('Getting subscription card offers');

    // Get all card names
    const cardNames = await this.page.locator(this.selectors.subscriptionCardName).allTextContents();

    // Get all card prices
    const cardPrices = await this.page.locator(this.selectors.subscriptionCardPriceValue).allTextContents();

    // Combine into array of objects
    const cards = [];
    for (let i = 0; i < Math.min(cardNames.length, cardPrices.length); i++) {
      cards.push({
        name: cardNames[i].trim(),
        price: cardPrices[i].trim()
      });
    }

    Logger.info(`Found ${cards.length} subscription cards`);
    return cards;
  }

  /**
   * Get all membership details (active subscription + available offers)
   * @returns {Promise<Object>}
   */
  async getAllMembershipDetails() {
    Logger.info('Getting all membership details');

    const details = {
      activeSubscription: {
        membershipType: await this.getActiveSubscriptionType(),
        expireDate: await this.getActiveSubscriptionExpireDate()
      },
      availableOffers: await this.getSubscriptionCards()
    };

    Logger.info('All membership details retrieved');
    return details;
  }
}

module.exports = RCloudPage;

