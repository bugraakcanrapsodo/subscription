# Stripe Subscription Testing Framework

A comprehensive data-driven testing framework for Rapsodo's Stripe-based subscription system. This framework provides automated testing capabilities for complex subscription lifecycle scenarios including purchases, cancellations, reactivations, refunds, and renewals across multiple subscription types and currencies.

## 🎯 Overview

This framework addresses a critical testing challenge: Stripe's test clocks cannot be programmatically advanced for Checkout-created subscriptions. Our hybrid approach combines:

- **Data-Driven Testing**: CSV-based test cases with direct mapping to manual test scenarios
- **Hybrid Automation**: Automated API testing with manual time advancement steps for Stripe test clocks
- **Multi-Level Verification**: User API, Admin API, and Stripe GUI verification for comprehensive validation
- **Location-Based Testing**: Mullvad VPN integration for testing region-specific subscription behavior
- **Browser Automation**: Docker/Playwright service with video recording and screenshot capture
- **Action-Based Architecture**: Reusable actions (purchase, cancel, verify, refund, advance time) defined in JSON

### Key Features

- ✅ **CSV Test Cases**: Easy-to-edit test cases in Excel/CSV format
- ✅ **Flexible Test Execution**: Run by test ID, tags (smoke, refund, renewal), or all tests
- ✅ **Comprehensive Reporting**: JSON and TXT reports with detailed step-by-step results
- ✅ **Video Recording**: All browser operations recorded for debugging
- ✅ **VPN Integration**: Automated VPN connection for location-based testing
- ✅ **Date Calculation**: Accurate subscription date calculations handling leap years
- ✅ **Manual Verification**: Pause execution for manual verification steps
- ✅ **XRay Integration**: Optional test case management and reporting

## 🛠 Tech Stack

### Core Technologies
- **Python 3.13+**: Test framework and business logic
- **Pytest**: Test runner and fixture management
- **Docker**: Containerized browser automation service
- **Node.js/Express**: Playwright service REST API

### Key Libraries
- **Playwright**: Browser automation for Stripe checkout flows
- **Mullvad VPN CLI**: Location-based testing

### Integrations
- **Stripe API**: Payment processing and test clock management
- **Rapsodo MLM API**: User and Admin API verification
- **XRay (Optional)**: Test case management
- **ReportPortal (Optional)**: Test execution reporting

## 📁 Project Structure

```
subscription/
├── api/                           # API Client Layer
│   ├── mlm_api.py                # Main MLM API client
│   ├── base_client.py            # Base HTTP client with retry logic
│   └── config.py                 # API endpoints and configuration
│
├── test_engine/                   # Test Execution Engine
│   ├── executor.py               # Main test executor
│   ├── actions.py                # Action handlers (purchase, cancel, verify, etc.)
│   ├── excel_reader.py           # CSV/Excel test case parser
│   ├── reporter.py               # JSON/TXT report generation
│   ├── user_verifier.py          # User API verification
│   ├── admin_verifier.py         # Admin API verification
│   ├── stripe_verifier.py        # Stripe GUI verification
│   ├── subscription_expectations.py  # Expected value calculator
│   └── location_manager.py       # VPN/location management
│
├── config/                        # Configuration Files
│   ├── actions.json              # Action definitions
│   ├── subscriptions.json        # Subscription metadata
│   ├── test_cards.json           # Stripe test card numbers
│   └── locations.json            # Country/currency mappings
│
├── data/                          # Test Data
│   └── premium_regression.csv    # Premium subscription tests
│
├── docker/playwright-service/     # Browser Automation Service
│   ├── src/
│   │   ├── pages/                # Page object models
│   │   ├── routes/               # REST API endpoints
│   │   ├── services/             # Checkout automation services
│   │   └── utils/                # Browser utilities
│   ├── output/                   # Test Artifacts
│   │   ├── videos/               # Recorded browser sessions
│   │   ├── screenshots/          # Page screenshots
│   │   └── logs/                 # Service logs
│   └── scripts/                  # Utility scripts
│
├── base/                          # Core Infrastructure
│   ├── logger.py                 # Centralized logging
│   ├── step_tracker.py           # Test step tracking
│   └── xray_api.py              # XRay integration
│
├── models/                        # Data Models
│   └── subscription.py           # Subscription data classes
│
├── utils/                         # Utilities
│   └── stripe_helper.py          # Stripe API helpers
│
├── tests/                         # Test Entry Points
│   └── test_data_driven.py       # Main data-driven test
│
├── test_results/                  # Test Reports (JSON + TXT)
├── logs/                          # Test Execution Logs
├── fixtures.py                    # Pytest fixtures
├── conftest.py                    # Pytest configuration
├── pytest.ini                     # Pytest settings
├── requirements.txt               # Python dependencies
└── .env                          # Environment variables
```

## 🚀 First-Time Setup Guide

### Prerequisites Check

Before starting, ensure you have:
- Mac OS (10.15 or later)
- Admin privileges to install software
- Internet connection
- At least 5GB free disk space

---

### Step 1: Install Homebrew (Package Manager)

Check whether Homebrew is installed:

```bash
brew --version
```

Open **Terminal** (Applications → Utilities → Terminal) and run:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Follow the on-screen instructions. After installation, verify:

```bash
brew --version
```

---

### Step 2: Install Python 3.13+

```bash
# Install Python 3.13
brew install python@3.13

# Verify installation
python3 --version  # Should show Python 3.13.x or higher
```

---

### Step 3: Install Docker Desktop

1. Download Docker Desktop for Mac: https://www.docker.com/products/docker-desktop/
2. Install by dragging to Applications folder
3. Launch Docker Desktop from Applications
4. Wait for Docker to start (whale icon in menu bar should be steady)

Verify installation:

```bash
docker --version
docker-compose --version
```

---

### Step 4: Install VS Code (Recommended)

1. Download VS Code: https://code.visualstudio.com/
2. Install by dragging to Applications folder
3. Launch VS Code
4. Install recommended extensions:
   - **Python** (by Microsoft)
   - **CSV Rainbow** (for colored CSV editing)
   - **Container Tools** (for container management)

To install extensions:
- Click Extensions icon (⇧⌘X) or View → Extensions
- Search for each extension and click Install

---

### Step 5: Clone the Repository

```bash
# Navigate to your development folder
cd ~/Development

# Clone the repository
git clone https://gitlab.com/rapsodoinc/tr/qa/test-automation/subscription.git
cd subscription
```

---

### Step 6: Create Python Virtual Environment

```bash
# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# You should see (.venv) prefix in your terminal
# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

**Note**: You'll need to activate the virtual environment every time you open a new terminal:

```bash
source .venv/bin/activate

# For deactivating the virtual environment execute following
deactivate
```

---

### Step 7: Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Create .env file
touch .env
```

Copy the contents of `.env.example` to `.env` in VS Code and replace placeholder values with actual credentials:

```bash
# ==================== Stripe Configuration ====================
# Stripe Test API Key (REQUIRED for refund and time advancement tests)
# Get your test key from: https://dashboard.stripe.com/test/apikeys
STRIPE_TEST_API_KEY=sk_test_YOUR_STRIPE_KEY_HERE

# ==================== MLM Admin Credentials ====================
# MLM Admin Email and Password (REQUIRED for admin API verification)
# Used to verify subscriptions via the admin panel API
MLM_ADMIN_EMAIL=your_admin_email@example.com
MLM_ADMIN_PASSWORD=your_admin_password

# ==================== Mullvad VPN Configuration ====================
# Mullvad Account Number (REQUIRED for VPN location-based testing)
# Get your 16-digit account number from: https://mullvad.net/en/account/
MULLVAD_ACCOUNT=your_account_number
```

---

### Step 8: Open Project in VS Code

#### VS Code Workspace Setup:

**Select Python Interpreter**:
- Press `⇧⌘P` (Shift+Command+P)
- Type "Python: Select Interpreter"
- Choose `.venv/bin/python`

**Configure Terminal**:
- VS Code will automatically activate `.venv` when opening new terminals

**Explore the Project**:
- `data/` - Test data (CSV files you'll edit)
- `logs/` - Test execution logs
- `test_results/` - JSON and TXT reports
- `docker/playwright-service/output/` - Videos & screenshots of browser operations
- `tests/` - Test cases. You'll use only `test_data_driven.py`

---

### Step 9: VS Code Local Execution

- Follow the [instructions here](https://code.visualstudio.com/docs/editor/debugging) to create a `launch.json` file and select **Python** as the environment

- Use the following configuration. Pytest arguments are explained below:
  - `-s`: Prevents capturing of output, allowing you to see print statements and logging in the console.
  - `-v`: Enables verbose output, providing detailed test results.
  - `"tests/test_data_driven.py"`: Specifies the main test file to run.
  - `--excel data/premium_regression.csv`: Specifies the target test csv file
  - `--test-tag refund`: Specifies the tags of tests to run. Only the tagged tests in test_tag column of csv file will be executed
  - `--test-id TC01`: Specifies the id of the test to run. Only the matching test in test_id column of csv file will be executed

```json
{
    // Use IntelliSense to learn about possible attributes.
    // Hover to view descriptions of existing attributes.
    // For more information, visit: https://go.microsoft.com/fwlink/?linkid=830387
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Pytest Data Driven",
            "type": "debugpy",
            "request": "launch",
            "module": "pytest",
            "args": [
                "-s",
                "-v",
                "tests/test_data_driven.py",
                "--excel",
                "data/premium_regression.csv",
                "--test-tag",
                "refund",
                "--test-id",
                "TC01"
            ],
            "console": "integratedTerminal",
            "cwd": "${workspaceFolder}",
            "python": "${workspaceFolder}/.venv/bin/python",
            "justMyCode": false,
            "preLaunchTask": "Start Docker Playwright Service",
            "postDebugTask": "Collect Docker Playwright Logs"
        }
    ]
}
```

- Create `tasks.json` in `.vscode` folder and add following code:

```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Start Docker Playwright Service",
            "type": "shell",
            "command": "${workspaceFolder}/docker/playwright-service/scripts/localrun.sh",
            "presentation": {
                "reveal": "always",
                "panel": "new"
            }
        },
        {
            "label": "Collect Docker Playwright Logs",
            "type": "shell",
            "command": "${workspaceFolder}/docker/playwright-service/scripts/collect_logs.sh",
            "presentation": {
                "reveal": "always",
                "panel": "new"
            },
            "problemMatcher": []
        }
    ]
}
```

- Start execution by pressing **F5** or going to the **Debug Tab** and clicking the **Play icon.**

#### Viewing Results:

After test execution, check the following files to understand the test execution results:

1. **Logs**:
   - `logs/test_run_YYYYMMDD_HHMMSS.log`

2. **Test Reports** (TXT):
   - `test_results/test_report_YYYYMMDD_HHMMSS.txt`

3. **Docker Videos**:
   - `docker/playwright-service/output/videos/`

4. **Docker Logs**:
   - `docker/playwright-service/output/logs/`

5. **Docker Screenshots**:
   - `docker/playwright-service/output/screenshots/`

#### Editing Test Cases (CSV):

1. Open CSV file in `data/` folder
2. CSV Rainbow extension colors columns for easy reading
3. Edit test data
4. Save with `⌘S`
5. Run tests again