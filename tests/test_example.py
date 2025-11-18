"""
Example test to verify the Playwright service is working correctly.
"""

import pytest
import requests


@pytest.mark.smoke
def test_playwright_service_health():
    """Test: Verify Playwright service is running and healthy"""
    
    # Health check endpoint
    url = "http://localhost:3001/api/health"
    
    response = requests.get(url)
    
    assert response.status_code == 200, f"Health check failed with status {response.status_code}"
    
    data = response.json()
    assert data['status'] == 'ok', "Service status is not ok"
    assert data['service'] == 'Playwright Service', "Service name mismatch"
    
    print(f"✓ Playwright service is healthy: {data}")


@pytest.mark.smoke
@pytest.mark.ui
def test_navigate_to_google():
    """Test: Navigate to Google and verify basic automation works
    
    This test verifies:
    - Browser automation is working
    - BasePage functions correctly
    - Screenshots and videos are captured
    """

    url = "http://localhost:3001/api/test/navigate"
    
    payload = {
        "url": "https://www.google.com",
        "waitTime": 5000  # Wait 5 seconds
    }
    
    print(f"\n🚀 Starting navigation test to {payload['url']}")
    
    response = requests.post(url, json=payload, timeout=30)
    
    assert response.status_code == 200, f"Navigation failed with status {response.status_code}"
    
    data = response.json()
    assert data['success'] is True, f"Navigation unsuccessful: {data.get('error', 'Unknown error')}"
    
    # Verify response data
    result = data['data']
    assert result['url'] == payload['url'], "URL mismatch"
    assert result['pageTitle'] is not None, "Page title not captured"
    assert result['screenshot'] is not None, "Screenshot not captured"
    
    print(f"✓ Navigation successful!")
    print(f"  - Page Title: {result['pageTitle']}")
    print(f"  - Screenshot: {result['screenshot']}")
    print(f"  - Video: {result.get('video', 'N/A')}")
    print(f"  - Wait Time: {result['waitTime']}ms")

