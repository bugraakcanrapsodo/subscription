const BaseService = require('./base-service');
const RCloudPage = require('../pages/rcloudPage');
const MediaUtils = require('../utils/media-utils');
const Logger = require('../utils/logger');

/**
 * Service for RCloud membership page automation
 */
class RCloudService {
  /**
   * Get membership details from RCloud profile page
   * @param {Object} membershipData - Contains authToken and userData
   * @returns {Promise<Object>} - Result with membership details
   */
  static async getMembershipDetails(membershipData) {
    // Validate required data
    if (!membershipData.authToken) {
      throw new Error('authToken is required in membershipData');
    }
    if (!membershipData.userData) {
      throw new Error('userData is required in membershipData');
    }

    // Execute with browser setup and cleanup
    return await BaseService.execute(
      // The automation function to run
      async (browser, context, page, data) => {
        // Set Local Storage for MLM domain
        Logger.info('Setting Local Storage for MLM domain');
        
        // Log all values that will be set
        Logger.info('Local Storage items to be set:');
        Logger.info(`  - mlmWebToken = ${data.authToken}`);
        Logger.info(`  - mlmWebVersion = 4.1.0`);
        Logger.info(`  - mlmWebSelectedUnit = mlm2`);
        Logger.info(`  - mlmWebUser = ${JSON.stringify(data.userData)}`);
        
        // Add Local Storage state to context for the MLM domain
        await context.addInitScript(({ authToken, userData }) => {
          // This script will run on every page load for mlm.rapsodo.com
          if (window.location.hostname.includes('mlm.rapsodo.com')) {
            localStorage.setItem('mlmWebToken', authToken);
            localStorage.setItem('mlmWebVersion', '4.1.0');
            localStorage.setItem('mlmWebSelectedUnit', 'mlm2');
            localStorage.setItem('mlmWebUser', JSON.stringify(userData));
          }
        }, { authToken: data.authToken, userData: data.userData });
        
        Logger.info('Local Storage init script added (4 items will be set when MLM domain loads)');
        
        // Create RCloudPage instance
        const rcloudPage = new RCloudPage(context, page);

        // Navigate to membership page
        await rcloudPage.navigateToMembershipPage();
        
        // Wait a bit for page to settle
        await page.waitForTimeout(2000);
        
        // Take screenshot of membership page
        const screenshotPath = await MediaUtils.takeScreenshot(
          page,
          'rcloud_membership_page',
          'membership'
        );

        // Get all membership details
        const membershipDetails = await rcloudPage.getAllMembershipDetails();
        
        Logger.info('Membership details retrieved:');
        Logger.info(`  Active: ${membershipDetails.activeSubscription.membershipType} (expires: ${membershipDetails.activeSubscription.expireDate})`);
        Logger.info(`  Offers: ${membershipDetails.availableOffers.length} cards found`);
        membershipDetails.availableOffers.forEach((card, index) => {
          Logger.info(`    ${index + 1}. ${card.name} - ${card.price}`);
        });

        // Return data to be included in the result
        return {
          message: 'Membership details retrieved successfully',
          data: {
            screenshot: screenshotPath,
            membershipDetails: membershipDetails
          }
        };
      },
      // Pass the input data
      membershipData,
      // Pass the operation name
      'get_membership_details'
    );
  }
}

module.exports = RCloudService;

