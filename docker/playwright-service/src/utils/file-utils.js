// utils/file-utils.js
const fs = require('fs');
const path = require('path');
const multer = require('multer');

/**
 * Utility class for file-related operations
 */
class FileUtils {
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
   * Create a storage configuration for multer file uploads
   * @param {string} destinationDir - Base directory for file uploads
   * @param {string} prefix - Filename prefix
   * @returns {multer.StorageEngine} - Configured storage engine
   */
  static createStorage(destinationDir = '/tmp/uploads', prefix = 'upload') {
    // Create directory if it doesn't exist
    if (!fs.existsSync(destinationDir)) {
      fs.mkdirSync(destinationDir, { recursive: true });
    }

    return multer.diskStorage({
      destination: (req, file, cb) => {
        cb(null, destinationDir);
      },
      filename: (req, file, cb) => {
        const timestamp = FileUtils.getSimplifiedTimestamp();
        const fileExt = path.extname(file.originalname);
        const filename = `${prefix}_${timestamp}${fileExt}`;
        cb(null, filename);
      }
    });
  }

  /**
   * Create a file filter function for multer
   * @param {Array<string>} allowedExtensions - List of allowed file extensions
   * @returns {Function} - File filter function
   */
  static createFileFilter(allowedExtensions = ['.xlsx', '.xls', '.csv']) {
    return (req, file, cb) => {
      const ext = path.extname(file.originalname).toLowerCase();
      if (allowedExtensions.includes(ext)) {
        cb(null, true);
      } else {
        cb(new Error(`Only ${allowedExtensions.join(', ')} files are allowed`), false);
      }
    };
  }

  /**
   * Clean up a file
   * @param {string} filePath - Path to the file
   * @returns {boolean} - True if the file was deleted, false otherwise
   */
  static cleanupFile(filePath) {
    try {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
        console.log(`File deleted: ${filePath}`);
        return true;
      }
      return false;
    } catch (error) {
      console.error(`Error deleting file ${filePath}: ${error.message}`);
      return false;
    }
  }
}

module.exports = FileUtils;