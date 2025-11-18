const express = require('express');
const router = express.Router();

/**
 * Health check endpoint
 */
router.get('/', (req, res) => {
  res.status(200).json({
    status: 'ok',
    service: 'Playwright Service',
    timestamp: new Date().toISOString()
  });
});

module.exports = router;


