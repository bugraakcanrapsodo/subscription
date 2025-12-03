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
   * @param {number} timeout - Navigation timeout in milliseconds (default: 60000)
   * @returns {Promise<void>}
   */
  async goto(url, timeout = 60000) {
    Logger.info(`Navigating to: ${url}`);
    await this.page.goto(url, { 
      timeout: timeout,
      waitUntil: 'load'
    });
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
   * Waits for element to be enabled if it's initially disabled
   * @param {string} locator - Element locator
   * @param {number} enabledTimeout - Time to wait for element to become enabled (default: 5000)
   * @returns {Promise<void>}
   */
  async click(locator, enabledTimeout = 5000) {
    const element = this.page.locator(locator);

    // Wait for element to become enabled if disabled
    if (await element.isDisabled()) {
      Logger.info(`Element ${locator} is disabled, waiting up to ${enabledTimeout}ms...`);
      await expect(element).toBeEnabled({ timeout: enabledTimeout });
    }

    // Attempt the click
    try {
      await element.click({ timeout: 2000 });
      Logger.debug(`Clicked element: ${locator}`);
    } catch (error) {
      Logger.warn(`Standard click failed for ${locator}, using JavaScript click fallback`);
      await element.evaluate(el => el.click());
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
   * @param {number} timeout - Timeout in milliseconds (default: 5000)
   * @returns {Promise<boolean>}
   */
  async isVisible(locator, timeout = 5000) {
    try {
      await this.page.waitForSelector(locator, { state: 'visible', timeout });
      return true;
    } catch (error) {
      return false;
    }
  }

  /**
   * Wait for any of the given locators to become visible and return the first one found
   * 
   * This method is useful when dealing with different possible UI paths where multiple
   * elements might appear in a given situation. It continuously checks for the presence
   * of any of the provided locators until one is found or the timeout is reached.
   * 
   * @param {Array<string>} locators - Array of CSS selectors to check
   * @param {number} timeout - Maximum time to wait in milliseconds (default: 10000)
   * @returns {Promise<string>} - The first locator that was found to be visible
   * @throws {Error} - If none of the elements appear within the timeout period
   * 
   * @example
   * // Wait for either old or new card accordion button
   * const cardButton = await page.waitForAnyElement([
   *   '[data-testid="card-accordion-item-button"]',
   *   '#payment-method-accordion-item-title-card'
   * ]);
   * await page.click(cardButton);
   */
  async waitForAnyElement(locators, timeout = 10000) {
    Logger.info(`Waiting for any of ${locators.length} element(s) to become visible (timeout: ${timeout}ms)`);
    Logger.debug(`Locators: ${locators.join(', ')}`);
    
    const endTime = Date.now() + timeout;
    const checkInterval = 500; // Check every 500ms
    
    while (Date.now() < endTime) {
      // Check each locator in sequence
      for (const locator of locators) {
        try {
          // Quick check with short timeout
          const isVisible = await this.page.locator(locator).isVisible({ timeout: checkInterval });
          if (isVisible) {
            Logger.info(`✓ Found visible element: ${locator}`);
            return locator;
          }
        } catch (error) {
          // Element not visible yet, continue to next locator
          continue;
        }
      }
      
      // Small sleep to prevent excessive CPU usage
      await this.page.waitForTimeout(checkInterval);
    }
    
    // If we get here, no element was found within the timeout
    const currentUrl = this.page.url();
    const errorMessage = `None of the expected elements appeared within ${timeout}ms.\n` +
                        `Looked for: ${locators.join(', ')}\n` +
                        `Current URL: ${currentUrl}`;
    Logger.error(errorMessage);
    throw new Error(errorMessage);
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