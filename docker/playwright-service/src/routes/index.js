const express = require('express');
const router = express.Router();

// Import routes
const healthRoutes = require('./healthRoutes');
const testRoutes = require('./testRoutes');

// Register routes
router.use('/health', healthRoutes);
router.use('/test', testRoutes);

// TODO: Add Stripe-specific routes
// const checkoutRoutes = require('./checkoutRoutes');
// const artifactRoutes = require('./artifactRoutes');
// router.use('/checkout', checkoutRoutes);
// router.use('/artifacts', artifactRoutes);

module.exports = router;
