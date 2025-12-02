const express = require('express');
const router = express.Router();

// Import routes
const healthRoutes = require('./healthRoutes');
const testRoutes = require('./testRoutes');
const checkoutRoutes = require('./checkoutRoutes');
const rcloudRoutes = require('./rcloudRoutes');

// Register routes
router.use('/health', healthRoutes);
router.use('/test', testRoutes);
router.use('/checkout', checkoutRoutes);
router.use('/rcloud', rcloudRoutes);

// TODO: Add artifact routes when needed
// const artifactRoutes = require('./artifactRoutes');
// router.use('/artifacts', artifactRoutes);

module.exports = router;
