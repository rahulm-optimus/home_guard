#!/usr/bin/env python3
"""
CostEstimatorAPI - Comprehensive Endpoint Testing Script
Tests all Azure Function endpoints with detailed output and error handling
Usage: python test_endpoints.py
"""

import requests
import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration
BASE_URL = "http://localhost:7071/api"

# ANSI color codes
class Colors:
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    GRAY = '\033[90m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Test results tracking
test_results = {
    'passed': 0,
    'failed': 0,
    'warnings': 0
}

# Helper functions for formatted output
def print_title(text: str):
    """Print a title with borders"""
    print(f"\n{Colors.CYAN}{'=' * 80}")
    print(f" {text}")
    print(f"{'=' * 80}{Colors.RESET}")

def print_test_header(number: str, text: str):
    """Print a test section header"""
    print(f"\n{Colors.YELLOW}[{number}] {text}")
    print(f"{Colors.GRAY}{'-' * 80}{Colors.RESET}")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}SUCCESS: {text}{Colors.RESET}")

def print_failure(text: str):
    """Print failure message"""
    print(f"{Colors.RED}FAILURE: {text}{Colors.RESET}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.BLUE}INFO: {text}{Colors.RESET}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}WARNING: {text}{Colors.RESET}")

def print_json(data: Any, indent: int = 2):
    """Print JSON data with formatting"""
    print(f"{Colors.GRAY}{json.dumps(data, indent=indent, default=str)}{Colors.RESET}")

def make_request(
    method: str,
    endpoint: str,
    description: str,
    body: Optional[Dict] = None,
    params: Optional[Dict] = None
) -> Optional[Dict]:
    """Make an HTTP request to the API with error handling"""
    global test_results
    
    url = f"{BASE_URL}{endpoint}"
    print_info(f"Requesting: {method} {url}")
    
    if params:
        print(f"{Colors.GRAY}Query Params: {params}{Colors.RESET}")
    
    if body:
        print(f"{Colors.GRAY}Request Body:{Colors.RESET}")
        print_json(body)
    
    try:
        response = requests.request(
            method=method,
            url=url,
            json=body,
            params=params,
            timeout=30
        )
        
        # Try to parse JSON response
        try:
            response_data = response.json()
        except:
            response_data = {"raw_response": response.text}
        
        if response.status_code >= 200 and response.status_code < 300:
            print_success(f"Success: {description}")
            print(f"{Colors.GRAY}Response:{Colors.RESET}")
            print_json(response_data)
            test_results['passed'] += 1
            return response_data
        else:
            print_failure(f"Failed: {description}")
            print(f"{Colors.RED}Status Code: {response.status_code}{Colors.RESET}")
            print(f"{Colors.RED}Response:{Colors.RESET}")
            print_json(response_data)
            test_results['failed'] += 1
            return None
            
    except requests.exceptions.ConnectionError:
        print_failure(f"Failed: {description}")
        print(f"{Colors.RED}Error: Connection refused. Is Azure Functions running?{Colors.RESET}")
        test_results['failed'] += 1
        return None
    except requests.exceptions.Timeout:
        print_failure(f"Failed: {description}")
        print(f"{Colors.RED}Error: Request timeout{Colors.RESET}")
        test_results['failed'] += 1
        return None
    except Exception as e:
        print_failure(f"Failed: {description}")
        print(f"{Colors.RED}Error: {str(e)}{Colors.RESET}")
        test_results['failed'] += 1
        return None

def check_service_running() -> bool:
    """Check if Azure Functions service is running"""
    print_info("Checking if Azure Functions is running...")
    try:
        response = requests.get(f"{BASE_URL}/../", timeout=5)
        print_success("Azure Functions is running")
        return True
    except:
        print_failure("Azure Functions may not be running")
        print_warning("Make sure to run 'func start' in the CostEstimatorAPI directory")
        return False

def test_save_items() -> Optional[Dict]:
    """Test 1: POST /v1/save-items"""
    print_test_header("1", "POST /v1/save-items - Save cost estimate items")
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    body = {
        "items": [
            {
                "thread_id": f"test-{timestamp}-001",
                "message": "Test: Replace damaged roof shingles",
                "zipcode": "94102",
                "min_estimate": 500,
                "max_estimate": 1200,
                "cluster_id": "1",
                "status": "estimate_complete"
            },
            {
                "thread_id": f"test-{timestamp}-002",
                "message": "Test: Repair water damaged drywall",
                "zipcode": "94105",
                "min_estimate": 300,
                "max_estimate": 800,
                "cluster_id": "1",
                "status": "ai_analyzed"
            }
        ]
    }
    
    result = make_request("POST", "/v1/save-items", "Save 2 test items", body=body)
    
    if result:
        print_info(f"Status: {result.get('status', 'unknown')}")
        print_info(f"Saved: {result.get('saved_count', 0)} items")
        if result.get('failed_count', 0) > 0:
            print_warning(f"Failed: {result.get('failed_count', 0)} items")
    
    return result

def test_get_items() -> Optional[str]:
    """Test 2: GET /v1/items"""
    print_test_header("2", "GET /v1/items - Get all items with pagination")
    
    result = make_request("GET", "/v1/items", "Get first 5 items", 
                         params={"offset": 0, "limit": 5})
    
    test_item_id = None
    if result and result.get('data', {}).get('items'):
        items = result['data']['items']
        print_info(f"Total items: {result['data'].get('total_count', 0)}")
        print_info(f"Returned: {result['data'].get('returned_count', 0)}")
        if len(items) > 0:
            test_item_id = items[0].get('id')
            print_info(f"Sample Item ID for later tests: {test_item_id}")
    
    return test_item_id

def test_get_clusters():
    """Test 3: GET /v1/clusters"""
    print_test_header("3", "GET /v1/clusters - Get all clusters")
    
    result = make_request("GET", "/v1/clusters", "Get first 5 clusters",
                         params={"offset": 0, "limit": 5})
    
    if result and result.get('data'):
        print_info(f"Total clusters: {result['data'].get('total_count', 0)}")
        print_info(f"Returned: {result['data'].get('returned_count', 0)}")
    
    # Test with search
    print(f"\n{Colors.BLUE}Testing cluster search...{Colors.RESET}")
    make_request("GET", "/v1/clusters", "Search clusters with 'Bay'",
                params={"search": "Bay", "offset": 0, "limit": 5})

def test_cluster_by_zipcode():
    """Test 4: GET /v1/cluster-by-zipcode"""
    print_test_header("4", "GET /v1/cluster-by-zipcode - Find cluster by zipcode")
    
    test_zipcodes = ["94102", "90210", "10001"]
    for zipcode in test_zipcodes:
        print(f"\n{Colors.BLUE}Testing zipcode: {zipcode}{Colors.RESET}")
        result = make_request("GET", "/v1/cluster-by-zipcode",
                            f"Find cluster for zipcode {zipcode}",
                            params={"zipcode": zipcode})
        
        if result and result.get('found'):
            print_info(f"Found cluster: {result.get('cluster_name')} (ID: {result.get('cluster_id')})")
        elif result:
            print_warning(f"No cluster found for zipcode {zipcode}")

def test_search_items():
    """Test 5: GET /v1/search-items"""
    print_test_header("5", "GET /v1/search-items - Search items by message")
    
    search_queries = ["roof", "paint", "water"]
    for query in search_queries:
        print(f"\n{Colors.BLUE}Searching for: '{query}'{Colors.RESET}")
        result = make_request("GET", "/v1/search-items",
                            f"Search items with '{query}'",
                            params={"search_query": query, "offset": 0, "limit": 5})
        
        if result and result.get('data'):
            print_info(f"Found: {result['data'].get('total_count', 0)} matching items")
            print_info(f"Returned: {result['data'].get('returned_count', 0)}")

def test_update_item(item_id: Optional[str]):
    """Test 6: PUT /v1/update-item/{item_id}"""
    print_test_header("6", "PUT /v1/update-item/{item_id} - Update an item")
    
    if not item_id:
        print_warning("Skipping update test - no item ID available")
        print_info("Run the save-items test first to create test data")
        test_results['warnings'] += 1
        return
    
    print_info(f"Using item ID: {item_id}")
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    body = {
        "message": f"UPDATED: Test item - {timestamp}",
        "zipcode": "94102",
        "min_estimate": 600,
        "max_estimate": 1500,
        "cluster_id": "1",
        "status": "ai_analyzed"
    }
    
    result = make_request("PUT", f"/v1/update-item/{item_id}",
                         f"Update item {item_id}", body=body)
    
    if result:
        print_success("Item updated successfully")
        
        # Verify the update
        print(f"\n{Colors.BLUE}Verifying update...{Colors.RESET}")
        verify_result = make_request("GET", "/v1/items",
                                    "Get items to verify update",
                                    params={"offset": 0, "limit": 100})
        
        if verify_result and verify_result.get('data', {}).get('items'):
            items = verify_result['data']['items']
            updated_item = next((item for item in items if item.get('id') == item_id), None)
            if updated_item:
                print_success("Verified: Item found after update")
                print_info(f"Updated message: {updated_item.get('message', 'N/A')}")
            else:
                print_warning("Could not find updated item in list")

def print_summary():
    """Print test summary"""
    print_test_header("SUMMARY", "Test Results")
    
    print(f"\n{Colors.BOLD}Test Statistics:{Colors.RESET}")
    print(f"  {Colors.GREEN}Passed:   {test_results['passed']}{Colors.RESET}")
    print(f"  {Colors.RED}Failed:   {test_results['failed']}{Colors.RESET}")
    print(f"  {Colors.YELLOW}Warnings: {test_results['warnings']}{Colors.RESET}")
    print(f"  Total:    {test_results['passed'] + test_results['failed']}")
    
    if test_results['failed'] == 0:
        print(f"\n{Colors.GREEN}All tests passed!{Colors.RESET}")
        return 0
    else:
        print(f"\n{Colors.YELLOW}Some tests failed. Review the output above for details.{Colors.RESET}")
        return 1

def main():
    """Main test execution"""
    print_title("CostEstimatorAPI - Endpoint Testing Suite")
    print(f"Base URL: {BASE_URL}")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Pre-flight check
    print_test_header("0", "Pre-flight Check")
    if not check_service_running():
        sys.exit(1)
    
    # Run all tests
    test_save_items()
    test_item_id = test_get_items()
    test_get_clusters()
    test_cluster_by_zipcode()
    test_search_items()
    test_update_item(test_item_id)
    
    # Print summary and exit
    exit_code = print_summary()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
