const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const Logger = require('./logger');

/**
 * Utility class for browser-related operations
 */
class BrowserUtils {
  /**
   * Initialize browser, context, and page
   * @param {boolean} debug - Whether to run in debug mode
   * @returns {Promise<{browser: Browser, context: BrowserContext, page: Page}>}
   */
  static async initBrowser(debug = false) {
    // Create directories if they don't exist
    const videosDir = path.join('/app/output/videos');
    const screenshotsDir = path.join('/app/output/screenshots');

    for (const dir of [videosDir, screenshotsDir]) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }

    // Launch browser
    const browser = await chromium.launch({
      headless: !debug,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-features=MacAppCodeSignClone'
      ]
    });

    // Create a browser context with video recording enabled
    const context = await browser.newContext({
      recordVideo: {
        dir: videosDir,
        size: { width: 1280, height: 720 }
      }
    });

    const page = await context.newPage();

    // Add event listeners for debugging
    page.on('console', msg => Logger.debug(`PAGE: ${msg.text()}`));
    page.on('pageerror', err => Logger.error(`PAGE ERROR: ${err.message}`));

    return { browser, context, page };
  }

  /**
   * Take a screenshot of the current page
   * @param {Page} page - Playwright page
   * @param {string} filename - Screenshot filename
   * @returns {Promise<string>} - Path to the screenshot
   */
  static async takeScreenshot(page, filename) {
    const screenshotsDir = path.join('/app/output/screenshots');
    const screenshotPath = path.join(screenshotsDir, filename);

    await page.screenshot({ path: screenshotPath });
    Logger.info(`Screenshot saved to: ${screenshotPath}`);

    return screenshotPath;
  }
}

module.exports = BrowserUtils;
