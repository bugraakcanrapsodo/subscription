const express = require('express');
const cors = require('cors');
const routes = require('./routes');
const Logger = require('./utils/logger');

const app = express();
const port = process.env.PORT || 3000;

// Enable CORS
app.use(cors());

// Middleware to parse JSON
app.use(express.json());

// Register all routes
app.use('/api', routes);

// Start server
app.listen(port, () => {
  Logger.info(`Stripe Playwright Service running on port ${port}`);
});