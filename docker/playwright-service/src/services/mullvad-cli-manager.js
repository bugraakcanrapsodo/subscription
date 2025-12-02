const { exec } = require('child_process');
const util = require('util');
const Logger = require('../utils/logger');

const execPromise = util.promisify(exec);

/**
 * Mullvad VPN Manager using Mullvad CLI
 * This is simpler than WireGuard direct approach - no config files needed!
 */
class MullvadCLIManager {
  constructor() {
    this.currentConnection = null;
    this.initialized = false;
  }
  
  /**
   * Initialize Mullvad CLI with account login
   * This should be called once when the service starts
   */
  async initialize() {
    if (this.initialized) {
      return { success: true, message: 'Already initialized' };
    }
    
    const account = process.env.MULLVAD_ACCOUNT;
    
    if (!account) {
      Logger.warn('⚠️  MULLVAD_ACCOUNT not set. VPN will not work!');
      Logger.warn('   Set it in docker-compose.yml or .env file');
      return { success: false, message: 'No account number provided' };
    }
    
    try {
      // Check if already logged in (device credentials persisted in volume)
      Logger.info('🔍 Checking Mullvad account status...');
      try {
        const { stdout } = await execPromise('mullvad account get');
        // Check if we have an active account (any account means logged in)
        if (stdout.includes('Account:') || stdout.includes('Expires:')) {
          Logger.info('✅ Already logged in to Mullvad account (device reused from volume)');
          Logger.info(`   Device credentials persisted`);
        } else {
          throw new Error('Not logged in');
        }
      } catch (checkError) {
        // Not logged in, need to login
        Logger.info('🔐 Logging into Mullvad account...');
        
        try {
          // Login to Mullvad account
          await execPromise(`mullvad account login ${account}`);
          Logger.info('✅ Mullvad account logged in successfully');
        } catch (loginError) {
          // Check if error is about too many devices
          if (loginError.message.includes('too many devices')) {
            Logger.error('❌ Too many devices on Mullvad account!');
            Logger.error('   Solution 1: Go to https://mullvad.net/en/account/ and remove old devices');
            Logger.error('   Solution 2: Use "mullvad account logout" on one of your devices');
            Logger.error('   Note: Docker volumes now persist device credentials to avoid this issue');
            throw new Error('Too many devices on account. Remove old devices from Mullvad account page.');
          }
          throw loginError;
        }
      }
      
      // Set tunnel protocol to WireGuard (faster than OpenVPN)
      await execPromise('mullvad relay set tunnel-protocol wireguard');
      Logger.info('✅ Tunnel protocol set to WireGuard');
      
      // Allow LAN traffic (critical for Docker host communication)
      await execPromise('mullvad lan set allow');
      Logger.info('✅ LAN traffic allowed (Docker host can communicate)');
      
      // Update relay list (important for first run)
      try {
        Logger.info('Updating relay list...');
        await execPromise('mullvad relay update');
        
        // Wait for relay list to actually load (it runs in background)
        // Reduced from 3s to 2s for faster initialization
        Logger.info('Waiting for relay list to load...');
        await this.sleep(2000);
        
        Logger.info('✅ Relay list updated');
      } catch (error) {
        Logger.warn(`⚠️  Could not update relay list: ${error.message}`);
      }
      
      this.initialized = true;
      
      return { success: true, message: 'Initialized successfully' };
      
    } catch (error) {
      Logger.error(`❌ Failed to initialize Mullvad: ${error.message}`);
      return { success: false, message: error.message };
    }
  }
  
  /**
   * Connect to Mullvad VPN country using CLI
   * @param {string} country - Country code (e.g., 'de', 'us', 'jp')
   * @returns {Promise<Object>} Connection result with IP info
   */
  async connect(country) {
    // Ensure initialized
    if (!this.initialized) {
      const initResult = await this.initialize();
      if (!initResult.success) {
        throw new Error('Failed to initialize Mullvad: ' + initResult.message);
      }
    }
    
    Logger.info(`🔒 Connecting to Mullvad VPN: ${country.toUpperCase()} (using CLI)`);
    
    // Disconnect existing connection (with timeout to prevent hang)
    if (this.currentConnection) {
      try {
        await this.disconnect();
      } catch (error) {
        Logger.warn(`Disconnect failed, continuing: ${error.message}`);
        this.currentConnection = null;
      }
    }
    
    try {
      // Set relay country using Mullvad CLI
      Logger.info(`Setting relay country to: ${country}`);
      await execPromise(`mullvad relay set location ${country}`);
      
      // Connect to VPN
      Logger.info('Connecting to VPN...');
      await execPromise('mullvad connect');
      
      // Wait for connection to establish (reduced from 15s to 12s)
      await this.waitForConnection(12);
      
      this.currentConnection = country;
      
      Logger.info(`✅ Connected to Mullvad VPN: ${country.toUpperCase()}`);
      
      // Verify actual external location
      const locationVerification = await this.verifyExternalLocation(country);
      if (!locationVerification.success) {
        Logger.warn(`⚠️  Location verification warning: ${locationVerification.message}`);
        Logger.warn(`   Expected: ${country.toUpperCase()}, Got: ${locationVerification.detectedCountry || 'unknown'}`);
        // Don't fail the connection, just warn - sometimes geolocation services have delays
      } else {
        Logger.info(`✅ Location verified: External IP is from ${locationVerification.detectedCountry.toUpperCase()}`);
        Logger.info(`   IP: ${locationVerification.ip}, City: ${locationVerification.city || 'N/A'}`);
      }
      
      return {
        success: true,
        country: country,
        message: `Connected to ${country.toUpperCase()}`,
        verification: locationVerification
      };
      
    } catch (error) {
      Logger.error(`❌ Mullvad VPN connection failed: ${error.message}`);
      
      // Cleanup on failure
      await this.disconnect();
      
      throw new Error(`Failed to connect to Mullvad VPN (${country}): ${error.message}`);
    }
  }
  
  /**
   * Disconnect from Mullvad VPN
   */
  async disconnect() {
    if (!this.currentConnection) {
      return { success: true, message: 'No active connection' };
    }
    
    Logger.info(`🔓 Disconnecting from Mullvad VPN: ${this.currentConnection.toUpperCase()}`);
    
    try {
      // Use timeout to prevent hanging
      const disconnectPromise = execPromise('mullvad disconnect');
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Disconnect timeout')), 5000)
      );
      
      await Promise.race([disconnectPromise, timeoutPromise]);
      
      this.currentConnection = null;
      Logger.info('✅ Mullvad VPN disconnected');
      
      return { success: true, message: 'Disconnected' };
      
    } catch (error) {
      Logger.warn(`⚠️  Disconnect warning: ${error.message}`);
      this.currentConnection = null;
      return { success: true, message: 'Forced disconnect' };
    }
  }
  
  /**
   * Wait for VPN connection to establish
   * @param {number} timeoutSeconds - Timeout in seconds
   */
  async waitForConnection(timeoutSeconds = 15) {
    Logger.info('Waiting for VPN connection...');
    
    for (let i = 0; i < timeoutSeconds; i++) {
      await this.sleep(1000);
      
      const status = await this.getStatus();
      if (status.connected) {
        Logger.info(`✓ Connection established (${i + 1}s)`);
        return true;
      }
    }
    
    throw new Error('VPN connection timeout');
  }
  
  /**
   * Check connection status using Mullvad CLI
   */
  async getStatus() {
    try {
      const { stdout } = await execPromise('mullvad status');
      
      // Parse output like: "Connected to se-sto-wg-004"
      const connected = stdout.toLowerCase().includes('connected');
      
      if (connected) {
        return {
          connected: true,
          country: this.currentConnection
        };
      }
      
      return {
        connected: false,
        country: null
      };
      
    } catch (error) {
      return {
        connected: false,
        country: null,
        error: error.message
      };
    }
  }
  
  /**
   * Verify external IP location matches expected country
   * Uses ip-api.com (free, no API key needed)
   * @param {string} expectedCountry - Expected country code (e.g., 'us', 'jp')
   * @returns {Promise<Object>} Verification result with detected location
   */
  async verifyExternalLocation(expectedCountry) {
    try {
      Logger.info(`🌍 Verifying external IP location...`);
      
      // Use curl to check external IP location (with 10s timeout)
      // ip-api.com returns JSON with country code, IP, city, etc.
      const { stdout } = await execPromise('curl -s --max-time 10 http://ip-api.com/json/', {
        timeout: 12000
      });
      
      const locationData = JSON.parse(stdout);
      
      if (locationData.status !== 'success') {
        return {
          success: false,
          message: 'Failed to get location data',
          error: locationData.message
        };
      }
      
      const detectedCountry = locationData.countryCode.toLowerCase();
      const ip = locationData.query;
      const city = locationData.city;
      const region = locationData.regionName;
      
      Logger.info(`   Detected IP: ${ip}`);
      Logger.info(`   Detected Location: ${city}, ${region}, ${locationData.country} (${detectedCountry.toUpperCase()})`);
      
      // Check if detected country matches expected
      if (detectedCountry === expectedCountry.toLowerCase()) {
        return {
          success: true,
          detectedCountry: detectedCountry,
          expectedCountry: expectedCountry.toLowerCase(),
          ip: ip,
          city: city,
          region: region,
          country: locationData.country,
          message: 'Location verified successfully'
        };
      } else {
        return {
          success: false,
          detectedCountry: detectedCountry,
          expectedCountry: expectedCountry.toLowerCase(),
          ip: ip,
          city: city,
          region: region,
          country: locationData.country,
          message: `Location mismatch: expected ${expectedCountry.toUpperCase()}, got ${detectedCountry.toUpperCase()}`
        };
      }
      
    } catch (error) {
      Logger.error(`Failed to verify external location: ${error.message}`);
      return {
        success: false,
        message: 'Location verification failed',
        error: error.message
      };
    }
  }
  
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

module.exports = new MullvadCLIManager();

