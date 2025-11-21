# Stripe Subscription Testing Framework

A Python testing framework for Stripe subscription testing, built by reusing proven infrastructure from **PRO 2.0** and **cloudApi** projects.

## 🎯 Overview

This framework provides the structure and reusable components for testing Stripe subscription workflows:

- **Reused from PRO 2.0**: Logger, Xray integration, Step tracker, fixture patterns
- **Reused from cloudApi**: Docker Playwright service, browser recording, scripts
- **API Framework**: Backend API clients for actions & verifications
- **Hybrid Testing**: Both UI automation (Playwright) and API testing capabilities
- **Clean Structure**: Organized folders ready for Stripe-specific implementation

## 📁 Project Structure

```
subscription_poc/
├── base/                          ✅ REUSED FROM PRO 2.0
│   ├── logger.py                 # Adapted (removed Appium)
│   ├── xray_api.py              # As-is
│   ├── step_tracker.py          # As-is
│   └── __init__.py              # Basic imports
│
├── api/                           ✅ API Clients (NEW)
│   ├── __init__.py              # Module exports
│   ├── config.py                # Environment & endpoints
│   ├── base_client.py           # Base HTTP client
│   ├── auth_api.py              # Authentication API
│   └── README.md                # API documentation
│
├── models/                        📝 TODO: Pydantic models
│   └── __init__.py              # Placeholder
│
├── utils/                         📝 TODO: Utilities
│   └── __init__.py              # Placeholder
│
├── docker/playwright-service/     ✅ REUSED FROM cloudApi
│   ├── config/
│   │   ├── Dockerfile           # As-is from cloudApi
│   │   └── docker-compose.yml   # Adapted (renamed service)
│   ├── scripts/
│   │   ├── cleanup.sh           # As-is from cloudApi
│   │   ├── collect_logs.sh      # As-is from cloudApi
│   │   └── localrun.sh          # As-is from cloudApi
│   ├── src/
│   │   ├── app.js               # As-is from cloudApi
│   │   ├── utils/               # ✅ REUSED from cloudApi
│   │   │   ├── browser-utils.js    # Browser recording
│   │   │   ├── file-utils.js       # File operations
│   │   │   └── media-utils.js      # Media processing
│   │   ├── routes/              # 📝 TODO: Stripe-specific
│   │   ├── services/            # 📝 TODO: Checkout automation
│   │   └── pages/               # 📝 TODO: Page objects
│   ├── output/                  # Artifacts directory
│   └── package.json             # As-is from cloudApi
│
├── tests/                         ✅ Test cases
│   ├── test_example.py          # Playwright service test
│   └── test_auth_api.py         # Authentication API tests
│
├── data/                          📝 TODO: Test data
├── conftest.py                    ✅ REUSED patterns from PRO 2.0
├── pytest.ini                     ✅ REUSED from PRO 2.0 (adapted)
├── .gitlab-ci.yml                 ✅ REUSED from PRO 2.0 (adapted)
├── requirements.txt               ✅ Basic dependencies
├── .gitignore                     ✅ Project exclusions
├── README.md                      # This file
├── IMPLEMENTATION_TODO.md         # What needs implementation
└── REUSED_COMPONENTS.md          # Detailed reuse summary
```

## 🚀 Quick Start

### 1. Setup Python Environment

```bash
cd subscription_poc

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Setup Docker Playwright Service

```bash
cd docker/playwright-service/config

# Start service (uses reused cloudApi config)
docker-compose up -d

# Check health
curl http://localhost:3001/api/health
```

### 3. Configure Environment

Create a `.env` file with required environment variables:

```bash
# API Configuration
TEST_ENV=test
API_TEST_URL=https://test.mlm.rapsodo.com
API_TIMEOUT=30

# Stripe Configuration (Required for time advancement tests)
STRIPE_TEST_API_KEY=sk_test_your_stripe_test_api_key_here

# ReportPortal (optional)
# RP_ENDPOINT=http://...
# RP_PROJECT=...
```

### 4. Run Tests

```bash
# Activate virtual environment
source .venv/bin/activate

# Run API tests
pytest tests/test_auth_api.py -v -s

# Run Playwright service test
pytest tests/test_example.py -v -s

# Run with markers
pytest -m "smoke and api" -v -s
```
