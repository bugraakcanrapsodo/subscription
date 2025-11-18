const express = require('express');
const router = express.Router();
const BaseService = require('../services/base-service');
const BasePage = require('../pages/basePage');
const MediaUtils = require('../utils/media-utils');

/**
 * Simple test route - Navigate to URL and wait
 * POST /api/test/navigate
 * Body: { "url": "https://google.com", "waitTime": 5000 }
 */
router.post('/navigate', async (req, res) => {
  const { url, waitTime = 5000 } = req.body;

  if (!url) {
    return res.status(400).json({
      success: false,
      error: 'URL is required'
    });
  }

  // Define the automation function following PRO 2.0 pattern
  const navigateAutomation = async (browser, context, page, data) => {
    // Create BasePage instance
    const basePage = new BasePage(context, page);

    // Navigate to URL
    await basePage.goto(data.url);

    // Take a screenshot after navigation
    const screenshotPath = await MediaUtils.takeScreenshot(
      page,
      'navigate',
      'test'
    );

    // Wait for specified time
    await basePage.wait(data.waitTime);

    // Get final page title
    const pageTitle = await page.title();

    // Return result data
    return {
      message: 'Navigation test completed',
      data: {
        url: data.url,
        pageTitle,
        waitTime: data.waitTime,
        screenshot: screenshotPath
      }
    };
  };

  // Execute using BaseService (handles browser lifecycle and video recording automatically)
  const result = await BaseService.execute(
    navigateAutomation,
    { url, waitTime },
    'navigate_test'
  );

  // Return response
  const statusCode = result.success ? 200 : 500;
  res.status(statusCode).json(result);
});

module.exports = router;


