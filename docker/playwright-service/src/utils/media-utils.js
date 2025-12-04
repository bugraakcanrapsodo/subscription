// utils/media-utils.js
const fs = require('fs');
const path = require('path');
const { exec } = require('child_process');
const util = require('util');
const Logger = require('./logger');

const execPromise = util.promisify(exec);

/**
 * Utility class for media-related operations (videos and screenshots)
 */
class MediaUtils {
  // Recording start time (unix seconds) - set by browser-utils
  static recordingStartTime = null;

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
   * Convert webm to mp4 using FFmpeg
   * @param {string} inputPath - Path to the webm file
   * @param {string} outputPath - Path for the mp4 output
   * @returns {Promise<string>} - Path to the converted mp4 (or original if conversion fails)
   */
  static async convertToMp4(inputPath, outputPath) {
    const startTime = Date.now();
    Logger.info(`Converting video: ${inputPath} -> ${outputPath}`);

    // Build FFmpeg command with optional timestamp overlay
    let ffmpegCmd;
    if (MediaUtils.recordingStartTime) {
      // Add wall-clock timestamp overlay in top-left corner
      const filter = `drawtext=fontsize=18:fontcolor=white:borderw=2:bordercolor=black:x=10:y=10:text='%{pts\\:localtime\\:${MediaUtils.recordingStartTime}}'`;
      ffmpegCmd = `ffmpeg -y -i "${inputPath}" -vf "${filter}" -c:v libx264 -preset fast -crf 23 -c:a aac "${outputPath}"`;
    } else {
      ffmpegCmd = `ffmpeg -y -i "${inputPath}" -c:v libx264 -preset fast -crf 23 -c:a aac "${outputPath}"`;
    }

    try {
      await execPromise(ffmpegCmd);

      const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);

      if (fs.existsSync(outputPath)) {
        const inputSize = (fs.statSync(inputPath).size / 1024 / 1024).toFixed(2);
        const outputSize = (fs.statSync(outputPath).size / 1024 / 1024).toFixed(2);
        Logger.info(`Video converted in ${elapsed}s (${inputSize}MB -> ${outputSize}MB)`);

        // Remove original webm file
        fs.unlinkSync(inputPath);
        Logger.debug(`Removed original webm: ${inputPath}`);

        return outputPath;
      } else {
        throw new Error('Output file was not created');
      }
    } catch (error) {
      Logger.error(`FFmpeg conversion failed: ${error.message}`);
      return inputPath; // Return original if conversion fails
    }
  }

  /**
   * Stop the video recording and convert to mp4
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
    
    // Create filenames for webm and mp4
    const webmFilename = `${timestamp}_${operation}.webm`;
    const mp4Filename = `${timestamp}_${operation}.mp4`;
    const webmPath = path.join(videosDir, webmFilename);
    const mp4Path = path.join(videosDir, mp4Filename);
    
    // Move the video to our custom path
    try {
      if (fs.existsSync(videoPath)) {
        Logger.info(`Renaming video from ${videoPath} to ${webmPath}`);
        fs.renameSync(videoPath, webmPath);
        Logger.debug(`Video renamed to: ${webmPath}`);
      } else {
        Logger.error(`Error: Original video file not found at ${videoPath}`);
        return {
          videoPath: videoPath,
          videoFilename: path.basename(videoPath)
        };
      }
    } catch (err) {
      Logger.error(`Error renaming video file: ${err.message}`);
      return {
        videoPath: videoPath,
        videoFilename: path.basename(videoPath)
      };
    }
    
    // Convert to mp4
    const finalPath = await MediaUtils.convertToMp4(webmPath, mp4Path);

    return {
      videoPath: finalPath,
      videoFilename: path.basename(finalPath)
    };
  }
}

module.exports = MediaUtils;