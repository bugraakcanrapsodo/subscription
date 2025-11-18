// utils/media-utils.js
const fs = require('fs');
const path = require('path');
const Logger = require('./logger');

/**
 * Utility class for media-related operations (videos and screenshots)
 */
class MediaUtils {
  /**
   * Helper method to generate a simplified timestamp
   * Format: YYYY-MM-DD_HH-MM-SS
   * @returns {string} - Formatted timestamp
   */
  static getSimplifiedTimestamp() {
    const now = new Date();

    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');

    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');

    return `${year}-${month}-${day}_${hours}-${minutes}-${seconds}`;
  }

  /**
   * Take a screenshot with timestamp
   * @param {Page} page - Playwright page
   * @param {string} operation - Operation type for the filename prefix
   * @param {string} description - Short description for the filename
   * @returns {Promise<string>} - Path to the screenshot
   */
  static async takeScreenshot(page, operation, description = 'screenshot') {
    const timestamp = MediaUtils.getSimplifiedTimestamp();
    const filename = `${operation}_${description}_${timestamp}.png`;
    const screenshotsDir = path.join('/app/output/screenshots');
    const screenshotPath = path.join(screenshotsDir, filename);

    // Create directory if it doesn't exist
    if (!fs.existsSync(screenshotsDir)) {
      fs.mkdirSync(screenshotsDir, { recursive: true });
    }

    await page.screenshot({ path: screenshotPath });
    Logger.info(`Screenshot saved to: ${screenshotPath}`);

    return screenshotPath;
  }

  /**
   * Stop the video recording and rename it to a more descriptive filename
   * @param {Page} page - Playwright page
   * @param {BrowserContext} context - Playwright browser context
   * @param {string} operation - Operation type
   * @returns {Promise<{videoPath: string, videoFilename: string}>}
   */
  static async finishVideo(page, context, operation) {
    const videosDir = path.join('/app/output/videos');

    // Create directory if it doesn't exist
    if (!fs.existsSync(videosDir)) {
      fs.mkdirSync(videosDir, { recursive: true });
    }

    // Create a timestamp for the video filename
    const timestamp = MediaUtils.getSimplifiedTimestamp();
    
    // Get the pending video path before closing context
    const pendingVideoPath = page.video().path();
    Logger.info(`Video is being recorded. Will get path after closing context.`);
    
    // Close context to ensure video is saved and the path is available
    await context.close();
    
    // Now resolve the path (it's only available after context is closed)
    const videoPath = await pendingVideoPath;
    Logger.info(`Original video saved at: ${videoPath}`);
    
    // Create a more descriptive filename
    const videoFilename = `${timestamp}_${operation}.webm`;
    const customVideoPath = path.join(videosDir, videoFilename);
    
    // Move the video to our custom path with better error handling
    try {
      if (fs.existsSync(videoPath)) {
        Logger.info(`Renaming video from ${videoPath} to ${customVideoPath}`);
        fs.renameSync(videoPath, customVideoPath);
        Logger.info(`Video successfully renamed to: ${customVideoPath}`);
      } else {
        Logger.error(`Error: Original video file not found at ${videoPath}`);
      }
    } catch (err) {
      Logger.error(`Error renaming video file: ${err.message}`);
      // If rename fails, use the original path
      return {
        videoPath: videoPath,
        videoFilename: path.basename(videoPath)
      };
    }
    
    return {
      videoPath: customVideoPath,
      videoFilename: videoFilename
    };
  }
}

module.exports = MediaUtils;