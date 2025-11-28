"""
Location Manager
Handles location-to-currency mapping
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from base.logger import Logger


class LocationManager:
    """
    Manages location configurations and currency mappings
    """
    
    def __init__(self):
        """
        Initialize location manager by loading locations.json
        """
        self.logger = Logger(__name__)
        self.locations_config = self._load_locations_config()
        self.locations = self.locations_config.get('locations', {})
        self.default_location = self.locations_config.get('default_location', 'us')
        self.default_currency = self.locations_config.get('default_currency', 'usd')
        
        self.logger.info(f"LocationManager initialized with {len(self.locations)} locations")
    
    def _load_locations_config(self) -> Dict[str, Any]:
        """Load locations configuration from config/locations.json"""
        config_path = Path(__file__).parent.parent / 'config' / 'locations.json'
        
        if not config_path.exists():
            self.logger.warning(f"Locations config not found: {config_path}")
            return {'locations': {}, 'default_location': 'us', 'default_currency': 'usd'}
        
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def get_currency_for_location(self, location: str) -> str:
        """
        Get currency code for a given location
        
        Args:
            location: Location code (e.g., 'us', 'ca', 'de')
            
        Returns:
            Currency code (e.g., 'usd', 'cad', 'eur')
            
        Example:
            >>> lm = LocationManager()
            >>> lm.get_currency_for_location('de')
            'eur'
            >>> lm.get_currency_for_location('us')
            'usd'
            >>> lm.get_currency_for_location('unknown')
            'usd'  # defaults to USD
        """
        location_lower = location.lower()
        location_info = self.locations.get(location_lower)
        
        if location_info:
            currency = location_info.get('currency', self.default_currency)
            self.logger.debug(f"Location '{location}' → Currency '{currency}'")
            return currency
        else:
            self.logger.warning(
                f"Location '{location}' not configured, defaulting to {self.default_currency}"
            )
            return self.default_currency
    
    def get_country_name_for_location(self, location: str) -> str:
        """
        Get country name for a given location
        
        Args:
            location: Location code (e.g., 'us', 'ca', 'de')
            
        Returns:
            Country name (e.g., 'United States', 'Canada', 'Germany')
            
        Example:
            >>> lm = LocationManager()
            >>> lm.get_country_name_for_location('de')
            'Germany'
            >>> lm.get_country_name_for_location('us')
            'United States'
            >>> lm.get_country_name_for_location('unknown')
            'UNKNOWN'  # defaults to uppercase location code
        """
        location_lower = location.lower()
        location_info = self.locations.get(location_lower)
        
        if location_info:
            name = location_info.get('name', location.upper())
            self.logger.debug(f"Location '{location}' → Name '{name}'")
            return name
        else:
            self.logger.warning(
                f"Location '{location}' not configured, using code as name"
            )
            return location.upper()
    
    def get_location_info(self, location: str) -> Dict[str, Any]:
        """
        Get complete location information
        
        Args:
            location: Location code (e.g., 'us', 'ca', 'de')
            
        Returns:
            Dictionary with location details (name, currency)
        """
        location_lower = location.lower()
        location_info = self.locations.get(location_lower)
        
        if location_info:
            return location_info.copy()
        else:
            # Return default location info
            return {
                'name': location.upper(),
                'currency': self.default_currency
            }
    
    def get_all_locations(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all configured locations
        
        Returns:
            Dictionary of all location configurations
        """
        return self.locations.copy()
    
    def get_locations_by_currency(self, currency: str) -> list:
        """
        Get all locations that use a specific currency
        
        Args:
            currency: Currency code (e.g., 'usd', 'eur')
            
        Returns:
            List of location codes using that currency
            
        Example:
            >>> lm = LocationManager()
            >>> lm.get_locations_by_currency('eur')
            ['de', 'fr', 'es', 'it', 'nl', ...]
        """
        currency_lower = currency.lower()
        matching_locations = []
        
        for loc_code, loc_info in self.locations.items():
            if loc_info.get('currency', '').lower() == currency_lower:
                matching_locations.append(loc_code)
        
        return matching_locations
    
    def validate_location(self, location: str) -> bool:
        """
        Check if a location is configured
        
        Args:
            location: Location code
            
        Returns:
            True if location is configured, False otherwise
        """
        return location.lower() in self.locations

