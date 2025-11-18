import logging
import os
from datetime import datetime
from io import BytesIO
from reportportal_client import RPLogger, RPLogHandler
import requests
import configparser
import os.path
import json

class Logger:
    _instance = None
    _initialized = False
    _rp_handler = None
    _error_logs = []  # Initialize class attribute

    # Default log levels
    DEFAULT_FILE_LEVEL = "DEBUG"
    DEFAULT_CONSOLE_LEVEL = "INFO"

    # Map string levels to logging constants
    LOG_LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, log_path=None, file_level=None, console_level=None):
        if not Logger._initialized:
            # Initialize error logs list
            Logger._error_logs = []
            
            # Use provided log path or default to 'logs' directory
            self.log_dir = log_path if log_path else 'logs'

            # Create logs directory if it doesn't exist
            os.makedirs(self.log_dir, exist_ok=True)

            # Create log file name with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f'test_run_{timestamp}.log'

            # Combine directory path with filename
            self.log_file = os.path.join(self.log_dir, log_filename)

            # Configure logger - do NOT use RPLogger, just use standard Logger
            self.logger = logging.getLogger('StripeTestAutomation')

            # Set propagate to False to prevent duplicate logs
            self.logger.propagate = False

            self.logger.setLevel(logging.DEBUG)  # Capture all logs

            # Clear any existing handlers to avoid duplicates
            self.logger.handlers.clear()

            # Convert string levels to logging constants
            file_log_level = self.LOG_LEVELS.get(
                (file_level or self.DEFAULT_FILE_LEVEL).upper(),
                self.LOG_LEVELS[self.DEFAULT_FILE_LEVEL]
            )
            console_log_level = self.LOG_LEVELS.get(
                (console_level or self.DEFAULT_CONSOLE_LEVEL).upper(),
                self.LOG_LEVELS[self.DEFAULT_CONSOLE_LEVEL]
            )

            # Create file handler
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setLevel(file_log_level)

            # Create console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(console_log_level)

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )

            # Add formatter to handlers
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            # Add handlers to logger
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)

            # Add ReportPortal handler
            if not any(isinstance(h, RPLogHandler) for h in self.logger.handlers):
                try:
                    rp_handler = RPLogHandler()
                    rp_handler.setLevel(logging.DEBUG)  # We need to capture all logs for ReportPortal
                    self.logger.addHandler(rp_handler)
                    Logger._rp_handler = rp_handler
                except Exception as e:
                    self.logger.warning(f"Failed to initialize ReportPortal handler: {str(e)}")
                    Logger._rp_handler = None

            Logger._initialized = True

    @classmethod
    def get_instance(cls, log_path=None, file_level=None, console_level=None):
        if cls._instance is None:
            cls._instance = Logger(log_path, file_level, console_level)
        return cls._instance

    @classmethod
    def _log_with_attachment(cls, level, message, attachment=None):
        """Internal method to handle logging with optional attachment"""
        instance = cls.get_instance()

        # Format extra data for logging
        extra = {}

        # Add attachments if available
        if attachment and cls._rp_handler:
            # Add custom attachment
            extra["attachment"] = attachment
            instance.logger.log(level, message, extra=extra)
        else:
            # No attachments
            instance.logger.log(level, message)

    @classmethod
    def debug(cls, message, attachment=None):
        """
        Log debug level message

        Args:
            message: The message to log
            attachment: Optional attachment to include with the log
        """
        cls._log_with_attachment(logging.DEBUG, message, attachment)

    @classmethod
    def info(cls, message, attachment=None):
        """
        Log info level message

        Args:
            message: The message to log
            attachment: Optional attachment to include with the log
        """
        cls._log_with_attachment(logging.INFO, message, attachment)

    @classmethod
    def warning(cls, message, attachment=None):
        """
        Log warning level message

        Args:
            message: The message to log
            attachment: Optional attachment to include with the log
        """
        cls._log_with_attachment(logging.WARNING, message, attachment)

    @classmethod
    def error(cls, message, attachment=None):
        """Log error level message"""
        cls._error_logs.append(message)
        cls._log_with_attachment(logging.ERROR, message, attachment)

    @classmethod
    def critical(cls, message, attachment=None):
        """Log critical level message"""
        cls._error_logs.append(message)
        cls._log_with_attachment(logging.CRITICAL, message, attachment)

    @classmethod
    def init_error_collection(cls):
        """Initialize or reset the error collection"""
        cls._error_logs = []

    @classmethod
    def get_error_summary(cls):
        """
        Return all collected error messages as a summary string.

        Returns:
            str: A formatted string containing all error messages
        """
        if not hasattr(cls, '_error_logs') or not cls._error_logs:
            return "No errors collected during test execution"

        summary_lines = []
        summary_lines.append("\n===== ERROR SUMMARY =====")

        for error_msg in cls._error_logs:
            summary_lines.append(f"{error_msg}")

        summary_lines.append("===== END ERROR SUMMARY =====")

        # Return the complete summary as a string
        return "\n".join(summary_lines)

    @classmethod
    def set_launch_attribute(cls, key, value):
        """
        Set an attribute for the current ReportPortal launch.
        This allows tracking key metrics like sync time in dashboards.

        Args:
            key (str): The attribute key
            value (str): The attribute value

        Returns:
            bool: True if successful, False otherwise
        """
        # Get ReportPortal configuration from pytest.ini
        try:
            config = configparser.ConfigParser()
            config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pytest.ini')
            config.read(config_file)

            # Debug logging to see what configuration is being read
            cls.get_instance().logger.debug(f"Reading ReportPortal config from: {config_file}")
            cls.get_instance().logger.debug(f"Config file exists: {os.path.exists(config_file)}")
            
            rp_endpoint = config.get('pytest', 'rp_endpoint')
            rp_project = config.get('pytest', 'rp_project')
            rp_api_key = config.get('pytest', 'rp_api_key')
            rp_launch = config.get('pytest', 'rp_launch', fallback='N/A')
            
            cls.get_instance().logger.debug(f"Config values - endpoint: {rp_endpoint}, project: {rp_project}, launch: {rp_launch}")
            cls.get_instance().logger.debug(f"API key (first 10 chars): {rp_api_key[:10] if rp_api_key else 'None'}...")

            # Use the API key directly as a bearer token
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {rp_api_key}'
            }

            # Get the latest launch
            get_url = f"{rp_endpoint}/api/v1/{rp_project}/launch/latest"
            response = requests.get(get_url, headers=headers)

            if response.status_code != 200:
                cls.get_instance().logger.error(f"Failed to get latest launch from ReportPortal: {response.status_code} - {response.text}")
                return False

            launch_data = response.json()

            cls.get_instance().logger.debug(f"Latest launch response data: {launch_data}")

            # Check the structure of the response to extract launch data
            launch = None
            if 'content' in launch_data and isinstance(launch_data['content'], list) and launch_data['content']:
                # Find the launch that matches the configured launch name
                for launch_item in launch_data['content']:
                    if launch_item.get('name') == rp_launch:
                        launch = launch_item
                        cls.get_instance().logger.debug(f"Found matching launch: {launch_item.get('name')} (ID: {launch_item.get('id')})")
                        break
                
                # If no matching launch found, log available launches and use the first one as fallback
                if not launch:
                    available_launches = [item.get('name') for item in launch_data['content']]
                    cls.get_instance().logger.warning(f"No launch found with name '{rp_launch}'. Available launches: {available_launches}")
                    cls.get_instance().logger.warning("Using first available launch as fallback")
                    launch = launch_data['content'][0]
                    
            elif isinstance(launch_data, dict) and 'id' in launch_data:
                launch = launch_data
            else:
                cls.get_instance().logger.error("Unexpected response format from ReportPortal")
                cls.get_instance().logger.debug(f"Response: {json.dumps(launch_data)}")
                return False

            launch_id = launch.get('id')
            if not launch_id:
                cls.get_instance().logger.error("No launch ID found in ReportPortal response")
                return False

            existing_attributes = launch.get('attributes', [])
            cls.get_instance().logger.debug(f"Found launch ID: {launch_id}")
            cls.get_instance().logger.debug(f"Existing attributes: {json.dumps(existing_attributes)}")

            # Create updated attributes list - replace existing key if found, otherwise add new
            updated_attributes = []
            key_found = False

            for attr in existing_attributes:
                if attr.get('key') == key:
                    # Update existing attribute
                    updated_attributes.append({
                        'key': key,
                        'value': value
                    })
                    key_found = True
                else:
                    # Keep existing attribute
                    updated_attributes.append(attr)

            # Add new attribute if key wasn't found
            if not key_found:
                updated_attributes.append({
                    'key': key,
                    'value': value
                })

            # Update the launch with the new attributes
            update_url = f"{rp_endpoint}/api/v1/{rp_project}/launch/{launch_id}/update"

            update_data = {
                'mode': 'DEFAULT',  # Include mode as per your cURL example
                'attributes': updated_attributes
            }

            update_response = requests.put(update_url, headers=headers, json=update_data)

            if update_response.status_code != 200:
                cls.get_instance().logger.error(f"Failed to update launch attributes in ReportPortal: {update_response.status_code} - {update_response.text}")
                return False

            cls.get_instance().logger.info(f"Successfully set launch attribute '{key}' to '{value}'")
            return True

        except Exception as e:
            cls.get_instance().logger.error(f"Error setting launch attribute in ReportPortal: {str(e)}")
            return False

    @classmethod
    def set_test_attribute(cls, key, value, test_name):
        """
        Set an attribute for a specific test item in ReportPortal.

        Args:
            key (str): The attribute key
            value (str): The attribute value
            test_name (str): The short name of the test (e.g., "test_stripe_checkout")

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            config = configparser.ConfigParser()
            config_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pytest.ini')
            config.read(config_file)

            # Debug logging to see what configuration is being read
            cls.get_instance().logger.debug(f"Reading ReportPortal config from: {config_file}")
            cls.get_instance().logger.debug(f"Config file exists: {os.path.exists(config_file)}")
            
            rp_endpoint = config.get('pytest', 'rp_endpoint')
            rp_project = config.get('pytest', 'rp_project')
            rp_api_key = config.get('pytest', 'rp_api_key')
            rp_launch = config.get('pytest', 'rp_launch', fallback='N/A')
            
            cls.get_instance().logger.debug(f"Config values - endpoint: {rp_endpoint}, project: {rp_project}, launch: {rp_launch}")
            cls.get_instance().logger.debug(f"API key (first 10 chars): {rp_api_key[:10] if rp_api_key else 'None'}...")

            # Use the API key directly as a bearer token
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {rp_api_key}'
            }

            # Step 1: Get the latest launch ID
            launch_url = f"{rp_endpoint}/api/v1/{rp_project}/launch/latest"
            launch_response = requests.get(launch_url, headers=headers)

            if launch_response.status_code != 200:
                cls.get_instance().logger.error(f"Failed to get latest launch from ReportPortal: {launch_response.status_code} - {launch_response.text}")
                return False

            launch_data = launch_response.json()

            cls.get_instance().logger.debug(f"Latest launch response data: {launch_data}")

            # Check the structure of the response to extract launch data
            launch = None
            if 'content' in launch_data and isinstance(launch_data['content'], list) and launch_data['content']:
                # Find the launch that matches the configured launch name
                for launch_item in launch_data['content']:
                    if launch_item.get('name') == rp_launch:
                        launch = launch_item
                        cls.get_instance().logger.debug(f"Found matching launch: {launch_item.get('name')} (ID: {launch_item.get('id')})")
                        break
                
                # If no matching launch found, log available launches and use the first one as fallback
                if not launch:
                    available_launches = [item.get('name') for item in launch_data['content']]
                    cls.get_instance().logger.warning(f"No launch found with name '{rp_launch}'. Available launches: {available_launches}")
                    cls.get_instance().logger.warning("Using first available launch as fallback")
                    launch = launch_data['content'][0]
                    
            elif isinstance(launch_data, dict) and 'id' in launch_data:
                launch = launch_data
            else:
                cls.get_instance().logger.error("Unexpected response format from ReportPortal")
                cls.get_instance().logger.debug(f"Response: {json.dumps(launch_data)}")
                return False

            launch_id = launch.get('id')
            if not launch_id:
                cls.get_instance().logger.error("No launch ID found in ReportPortal response")
                return False

            cls.get_instance().logger.debug(f"Found launch ID: {launch_id}")

            # Step 2: Search for the test item across all pages
            test_item = None
            page_size = 50  # Start with a reasonable page size
            current_page = 1

            while test_item is None:
                items_url = f"{rp_endpoint}/api/v1/{rp_project}/item?filter.eq.launchId={launch_id}&page.page={current_page}&page.size={page_size}"
                items_response = requests.get(items_url, headers=headers)

                if items_response.status_code != 200:
                    cls.get_instance().logger.error(f"Failed to get test items from ReportPortal: {items_response.status_code} - {items_response.text}")
                    return False

                items_data = items_response.json()

                cls.get_instance().logger.debug(f"Searching page {current_page} for test '{test_name}'")

                # Search for the test item in current page
                for item in items_data.get('content', []):
                    full_name = item.get('name', '')
                    # Extract the short test name from the full name
                    if '::' in full_name:
                        short_name = full_name.split('::')[-1]
                        if short_name == test_name:
                            test_item = item
                            cls.get_instance().logger.debug(f"Found test '{test_name}' on page {current_page}")
                            break

                # If test found, break out of the while loop
                if test_item:
                    break

                # Check if there are more pages
                page_info = items_data.get('page', {})
                total_pages = page_info.get('totalPages', 1)
                current_page_num = page_info.get('number', 1)

                cls.get_instance().logger.debug(f"Page {current_page_num} of {total_pages} searched")

                if current_page_num >= total_pages:
                    # No more pages to search
                    cls.get_instance().logger.debug(f"Reached last page ({total_pages}), test '{test_name}' not found")
                    break

                # Move to next page
                current_page += 1

            if not test_item:
                cls.get_instance().logger.error(f"Test item with short name '{test_name}' not found in the current launch")
                return False

            item_id = test_item.get('id')
            cls.get_instance().logger.debug(f"Found test item ID: {item_id} for test: {test_name}")

            # Get existing attributes for this test item
            existing_attributes = test_item.get('attributes', [])
            cls.get_instance().logger.debug(f"Existing test attributes: {json.dumps(existing_attributes)}")

            # Create updated attributes list - replace existing key if found, otherwise add new
            updated_attributes = []
            key_found = False

            for attr in existing_attributes:
                if attr.get('key') == key:
                    # Update existing attribute
                    updated_attributes.append({
                        'key': key,
                        'value': value
                    })
                    key_found = True
                else:
                    # Keep existing attribute
                    updated_attributes.append(attr)

            # Add new attribute if key wasn't found
            if not key_found:
                updated_attributes.append({
                    'key': key,
                    'value': value
                })

            # Update the test item with the new attributes
            update_url = f"{rp_endpoint}/api/v1/{rp_project}/item/{item_id}/update"

            update_data = {
                'attributes': updated_attributes
            }

            update_response = requests.put(update_url, headers=headers, json=update_data)

            if update_response.status_code != 200:
                cls.get_instance().logger.error(f"Failed to update test attributes in ReportPortal: {update_response.status_code} - {update_response.text}")
                return False

            cls.get_instance().logger.info(f"Successfully set test attribute '{key}' to '{value}' for test '{test_name}'")
            return True

        except Exception as e:
            cls.get_instance().logger.error(f"Error setting test attribute in ReportPortal: {str(e)}")
            return False

