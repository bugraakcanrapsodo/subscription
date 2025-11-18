const BrowserUtils = require('../utils/browser-utils');
const MediaUtils = require('../utils/media-utils');
const Logger = require('../utils/logger');

/**
 * Base service class that encapsulates common browser initialization and cleanup
 * This pattern is reused from PRO 2.0 for consistent service structure
 */
class BaseService {
  /**
   * Execute an automation function with browser setup and cleanup
   * @param {Function} automationFunction - The function to execute with (browser, context, page)
   * @param {Object} data - Data to pass to the automation function
   * @param {string} operation - Name of the operation being performed
   * @returns {Promise<Object>} - Result of the automation operation
   */
  static async execute(automationFunction, data, operation) {
    // Check if we're running in debug mode
    const isDebugMode = process.env.DEBUG_MODE === 'true';
    Logger.info(`Starting operation: ${operation} (Debug mode: ${isDebugMode ? 'ON' : 'OFF'})`);

    // Initialize browser, context, and page
    let browser, context, page;
    try {
      // Initialize browser with utils
      ({ browser, context, page } = await BrowserUtils.initBrowser(isDebugMode));
      
      // Execute the automation function
      const result = await automationFunction(browser, context, page, data);
      
      // Record video for debugging purposes, but don't include in the response
      await MediaUtils.finishVideo(page, context, operation);
      
      // Return success result without video information
      return {
        success: true,
        message: result.message || 'Operation completed successfully',
        ...result
      };
    } catch (error) {
      Logger.error(`Error in ${operation}: ${error.message}`);

      try {
        // Still record the error video for debugging, but don't include in the response
        if (page && page.video()) {
          try {
            await MediaUtils.finishVideo(page, context, `error_${operation}`);
          } catch (videoErr) {
            Logger.error(`Error handling video in error case: ${videoErr.message}`);
          }
        }

        // Return error response without video information
        return {
          success: false,
          message: error.message
        };
      } catch (e) {
        Logger.error(`Failed to handle error properly: ${e.message}`);
        return {
          success: false,
          message: error.message
        };
      }
    } finally {
      // Clean up: close browser (only if it's still open)
      try {
        if (browser) {
          await browser.close();
          Logger.info(`Browser closed for operation: ${operation}`);
        }
      } catch (closeError) {
        Logger.error(`Error closing browser: ${closeError.message}`);
      }
    }
  }
}

module.exports = BaseService;