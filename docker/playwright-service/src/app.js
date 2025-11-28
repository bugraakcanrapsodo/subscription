const express = require('express');
const cors = require('cors');
const routes = require('./routes');
const Logger = require('./utils/logger');
const mullvadVPN = require('./services/mullvad-cli-manager');

const app = express();
const port = process.env.PORT || 3000;

// Enable CORS
app.use(cors());

// Middleware to parse JSON
app.use(express.json());

// Register all routes
app.use('/api', routes);

// Start server
app.listen(port, async () => {
  Logger.info(`Stripe Playwright Service running on port ${port}`);
  
  // Initialize Mullvad VPN in background (non-blocking)
  // This happens during the 15-second wait in localrun.sh
  if (process.env.VPN_ENABLED === 'true' && process.env.MULLVAD_ACCOUNT) {
    Logger.info('🚀 Initializing Mullvad VPN in background...');
    mullvadVPN.initialize()
      .then(result => {
        if (result.success) {
          Logger.info('✅ Mullvad VPN ready for use');
        } else {
          Logger.warn(`⚠️  Mullvad VPN initialization failed: ${result.message}`);
        }
      })
      .catch(error => {
        Logger.error(`❌ Mullvad VPN initialization error: ${error.message}`);
      });
  } else {
    Logger.info('ℹ️  VPN disabled or MULLVAD_ACCOUNT not set');
  }
});