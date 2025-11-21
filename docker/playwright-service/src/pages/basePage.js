// pages/basePage.js
const fs = require('fs');
const path = require('path');
const Logger = require('../utils/logger');

/**
 * Base page class that all other page objects will extend
 */
class BasePage {
  /**
   * Create a new BasePage instance
   * @param {object} context - Playwright browser context
   * @param {object} page - Playwright page
   */
  constructor(context, page) {
    this.context = context;
    this.page = page;
    this.videosDir = path.join('/app/output/videos');
    this.screenshotsDir = path.join('/app/output/screenshots');

    // Create directories if they don't exist
    for (const dir of [this.videosDir, this.screenshotsDir]) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }
  }

  /**
   * Navigate to a URL
   * @param {string} url - URL to navigate to
   * @returns {Promise<void>}
   */
  async goto(url) {
    Logger.info(`Navigating to: ${url}`);
    await this.page.goto(url);
  }

  /**
   * Get the current value of an input field
   * @param {string} locator - Element locator
   * @returns {Promise<string>} - Current value of the input
   */
  async getInputValue(locator) {
    return await this.page.locator(locator).inputValue();
  }

  /**
   * Clear an input field
   * @param {string} locator - Element locator
   * @returns {Promise<void>}
   */
  async clearInput(locator) {
    await this.page.locator(locator).clear();
  }

  /**
   * Get text content from an element
   * @param {string} locator - Element locator
   * @returns {Promise<string>}
   */
  async getText(locator) {
    return await this.page.locator(locator).textContent();
  }

  /**
   * Get text content from an element, or null if element not found
   * Useful for optional elements that may not exist on all page types
   * @param {string} locator - Element locator
   * @param {number} timeout - Timeout in milliseconds (default: 2000)
   * @returns {Promise<string|null>}
   */
  async getTextOrNull(locator, timeout = 2000) {
    try {
      await this.page.waitForSelector(locator, { timeout });
      return await this.getText(locator);
    } catch (e) {
      return null;
    }
  }

  /**
   * Wait for a specific amount of time
   * @param {number} milliseconds - Time to wait in milliseconds
   * @returns {Promise<void>}
   */
  async wait(milliseconds) {
    Logger.info(`Waiting for ${milliseconds}ms`);
    await this.page.waitForTimeout(milliseconds);
  }

  /**
   * Enter text into an input field (always clears first)
   * @param {string} locator - Element locator
   * @param {string} value - Value to enter
   * @returns {Promise<void>}
   */
  async enter(locator, value) {
    const element = this.page.locator(locator);
    await element.clear();
    await element.fill(value);
  }

  /**
   * Click on an element with fallback to JavaScript click
   * Tries standard Playwright click first, falls back to JS click if visibility checks fail
   * @param {string} locator - Element locator
   * @returns {Promise<void>}
   */
  async click(locator) {
    try {
      // Try standard Playwright click (with actionability checks)
      await this.page.locator(locator).click({ timeout: 2000 });
      Logger.debug(`Clicked element: ${locator}`);
    } catch (error) {
      // If standard click fails (visibility/actionability issues), use JavaScript click
      Logger.warn(`Standard click failed for ${locator}, using JavaScript click fallback`);
      await this.page.locator(locator).evaluate(el => el.click());
      Logger.debug(`JavaScript click successful: ${locator}`);
    }
  }

  /**
   * Scroll element into view
   * @param {string} locator - Element locator
   * @param {string} behavior - Scroll behavior: 'smooth' or 'auto'
   * @returns {Promise<void>}
   */
  async scrollIntoView(locator, behavior = 'smooth') {
    const element = this.page.locator(locator);
    await element.scrollIntoViewIfNeeded();
    await this.page.waitForTimeout(300); // Brief pause for smooth scrolling
  }

  /**
   * Scroll to a specific section by text or heading
   * @param {string} sectionText - Text of the section heading
   * @returns {Promise<void>}
   */
  async scrollToSection(sectionText) {
    Logger.info(`Scrolling to section: ${sectionText}`);
    const sectionLocator = `text=${sectionText}`;
    await this.scrollIntoView(sectionLocator);
  }

  /**
   * Wait for an element to be visible
   * @param {string} locator - Element locator
   * @param {number} timeout - Timeout in milliseconds
   * @returns {Promise<void>}
   */
  async waitForVisible(locator, timeout = 30000) {
    await this.page.waitForSelector(locator, { state: 'visible', timeout });
  }

  /**
   * Wait for navigation to a specific URL
   * @param {string} url - URL to wait for
   * @param {number} timeout - Timeout in milliseconds
   * @returns {Promise<void>}
   */
  async waitForUrl(url, timeout = 30000) {
    await this.page.waitForURL(url, { timeout });
  }

  /**
   * Check if an element is visible
   * @param {string} locator - Element locator
   * @returns {Promise<boolean>}
   */
  async isVisible(locator) {
    return await this.page.locator(locator).isVisible();
  }

  /**
  * Handle file upload via file browser dialog
  * @param {string} triggerElementLocator - Locator for the element that opens the file dialog
  * @param {string} filePath - Path to the file to upload
  * @param {number} waitTime - Optional wait time after upload (in ms)
  * @returns {Promise<void>}
  */
  async uploadFile(triggerElementLocator, filePath, waitTime = 1000) {
    Logger.info(`Preparing to upload file: ${filePath}`);

    // Set up file chooser promise BEFORE clicking the button
    const fileChooserPromise = this.page.waitForEvent('filechooser');

    // Click the button that triggers the file dialog
    await this.click(triggerElementLocator);

    await this.page.waitForTimeout(500);

    // Handle the file chooser dialog
    const fileChooser = await fileChooserPromise;

    // Set the file to upload
    await fileChooser.setFiles(filePath);
    Logger.info(`File selected for upload: ${filePath}`);

    // Wait for the specified time after upload for processing
    if (waitTime > 0) {
      Logger.info(`Waiting ${waitTime}ms for file to be processed...`);
      await this.page.waitForTimeout(waitTime);
    }
  }

  /**
   * Get selector with dynamic value(s) filled in
   * @param {string} selectorTemplate - Selector template with {} placeholders
   * @param {...string} values - Values to fill in the template
   * @returns {string} Formatted selector
   */
  getOptionSelector(selectorTemplate, ...values) {
    let selector = selectorTemplate;
    values.forEach(value => {
      selector = selector.replace('{}', value);
    });
    Logger.debug(`Formatted selector: ${selector}`);
    return selector;
  }

}

module.exports = BasePage;