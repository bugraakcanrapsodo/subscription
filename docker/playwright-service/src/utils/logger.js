// utils/logger.js

/**
 * Simple logger with timestamps
 */
class Logger {
  /**
   * Get current timestamp in readable format
   * @returns {string} - Formatted timestamp
   */
  static getTimestamp() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    const ms = String(now.getMilliseconds()).padStart(3, '0');
    
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${ms}`;
  }

  /**
   * Log info message with timestamp
   * @param {string} message - Message to log
   */
  static info(message) {
    console.log(`[${this.getTimestamp()}] [INFO] ${message}`);
  }

  /**
   * Log error message with timestamp
   * @param {string} message - Error message to log
   */
  static error(message) {
    console.error(`[${this.getTimestamp()}] [ERROR] ${message}`);
  }

  /**
   * Log warning message with timestamp
   * @param {string} message - Warning message to log
   */
  static warn(message) {
    console.warn(`[${this.getTimestamp()}] [WARN] ${message}`);
  }

  /**
   * Log debug message with timestamp
   * @param {string} message - Debug message to log
   */
  static debug(message) {
    console.debug(`[${this.getTimestamp()}] [DEBUG] ${message}`);
  }
}

module.exports = Logger;

