const express = require('express');
const router = express.Router();
const RCloudService = require('../services/rcloud-service');
const Logger = require('../utils/logger');

/**
 * Get membership details from RCloud profile page
 * POST /api/rcloud/membership-details
 * Body: {
 *   "authToken": "JWT eyJ..." (required),
 *   "userData": {...} (required, user object from login response)
 * }
 */
router.post('/membership-details', async (req, res) => {
  try {
    const { authToken, userData } = req.body;

    // Validate required fields
    if (!authToken) {
      return res.status(400).json({
        success: false,
        error: 'Missing required field: authToken'
      });
    }

    if (!userData) {
      return res.status(400).json({
        success: false,
        error: 'Missing required field: userData'
      });
    }

    // Validate userData is an object
    if (typeof userData !== 'object' || Array.isArray(userData)) {
      return res.status(400).json({
        success: false,
        error: 'Invalid userData. Must be an object.'
      });
    }

    // Validate authToken format
    if (typeof authToken !== 'string' || !authToken.trim()) {
      return res.status(400).json({
        success: false,
        error: 'Invalid authToken. Must be a non-empty string.'
      });
    }

    Logger.info('Processing membership details request');

    // Prepare membership data
    const membershipData = {
      authToken: authToken.trim(),
      userData: userData
    };

    // Call the RCloud service to handle the automation
    const result = await RCloudService.getMembershipDetails(membershipData);

    // Return response based on result
    if (result.success) {
      return res.status(200).json(result);
    } else {
      return res.status(500).json(result);
    }
  } catch (error) {
    Logger.error(`Error getting membership details: ${error.message}`);
    return res.status(500).json({
      success: false,
      error: 'Failed to get membership details',
      message: error.message
    });
  }
});

module.exports = router;

