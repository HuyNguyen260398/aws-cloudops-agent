"""
Test script for the updated lambda_domain_monitor
Verifies that it correctly forwards events to the invoke handler
"""

import json
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# Mock context object
class MockContext:
    function_name = "test-domain-monitor"
    request_id = "test-request-123"


# Mock Lambda client
class MockLambdaClient:
    def __init__(self):
        self.invoked = False
        self.payload = None

    def invoke(self, **kwargs):
        self.invoked = True
        self.payload = json.loads(kwargs.get("Payload", "{}"))
        print(f"✅ Mock Lambda invoked with:")
        print(f"   Function: {kwargs.get('FunctionName')}")
        print(f"   Type: {kwargs.get('InvocationType')}")
        print(f"   Payload: {json.dumps(self.payload, indent=2)}")
        return {"StatusCode": 200}


# Mock boto3
class MockBoto3:
    lambda_client = MockLambdaClient()

    @staticmethod
    def client(service_name):
        if service_name == "lambda":
            return MockBoto3.lambda_client
        raise ValueError(f"Unknown service: {service_name}")


# Patch the imports
import src.lambdas.lambda_domain_monitor as monitor_module

monitor_module.boto3 = MockBoto3()

# Set environment variables
os.environ["INVOKE_LAMBDA_NAME"] = "test-invoke-handler"
os.environ["DOMAIN_TO_MONITOR"] = "test.example.com"


def test_successful_domain_check():
    """Test when domain is reachable"""
    print("\n" + "=" * 60)
    print("TEST 1: Successful Domain Check")
    print("=" * 60)

    # Mock socket to simulate success
    import socket

    original_gethostbyname = socket.gethostbyname

    def mock_gethostbyname_success(hostname):
        return "1.2.3.4"  # Return a mock IP

    socket.gethostbyname = mock_gethostbyname_success
    monitor_module.socket = socket

    # Reset the mock
    MockBoto3.lambda_client.invoked = False
    MockBoto3.lambda_client.payload = None

    # This should not invoke the handler
    result = monitor_module.lambda_handler({}, MockContext())

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "healthy" in body["message"]
    assert not MockBoto3.lambda_client.invoked, "Should not invoke handler on success"
    print("✅ TEST PASSED: Domain check successful, no handler invoked")

    # Restore original function
    socket.gethostbyname = original_gethostbyname


def test_domain_failure():
    """Test when domain is unreachable"""
    print("\n" + "=" * 60)
    print("TEST 2: Domain Failure Detection")
    print("=" * 60)

    # Mock socket to simulate failure
    import socket

    original_gethostbyname = socket.gethostbyname

    def mock_gethostbyname(hostname):
        raise socket.gaierror("Name or service not known")

    socket.gethostbyname = mock_gethostbyname
    monitor_module.socket = socket

    # Reset the mock
    MockBoto3.lambda_client.invoked = False
    MockBoto3.lambda_client.payload = None

    # This should invoke the handler
    result = monitor_module.lambda_handler({}, MockContext())

    # Verify the result
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "forwarded for analysis" in body["message"]
    assert MockBoto3.lambda_client.invoked, "Should invoke handler on failure"

    # Verify the payload structure
    payload = MockBoto3.lambda_client.payload
    assert payload["service_name"] == "test.example.com"
    assert payload["service_type"] == "Domain/Website"
    assert payload["issue_type"] == "domain_unreachable"
    assert payload["severity"] == "critical"
    assert payload["status"] == "DOWN"
    assert "context" in payload
    assert "metadata" in payload

    # Verify context
    context = payload["context"]
    assert "aws_services" in context
    assert "Amazon Route 53" in context["aws_services"]
    assert "infrastructure_info" in context
    assert "monitoring_source" in context
    assert context["monitoring_source"] == "lambda_domain_monitor"

    # Verify metadata
    metadata = payload["metadata"]
    assert metadata["domain"] == "test.example.com"
    assert "timestamp" in metadata
    assert metadata["lambda_function"] == "test-domain-monitor"
    assert metadata["request_id"] == "test-request-123"

    print("✅ TEST PASSED: Domain failure detected and forwarded correctly")
    print(f"\nEvent payload structure:")
    print(json.dumps(payload, indent=2))

    # Restore original function
    socket.gethostbyname = original_gethostbyname


def test_missing_environment_variable():
    """Test when INVOKE_LAMBDA_NAME is not set"""
    print("\n" + "=" * 60)
    print("TEST 3: Missing Environment Variable")
    print("=" * 60)

    # Save original value
    original_value = os.environ.get("INVOKE_LAMBDA_NAME")

    # Remove environment variable
    if "INVOKE_LAMBDA_NAME" in os.environ:
        del os.environ["INVOKE_LAMBDA_NAME"]

    # Mock socket to simulate failure
    import socket

    def mock_gethostbyname(hostname):
        raise socket.gaierror("Name or service not known")

    socket.gethostbyname = mock_gethostbyname
    monitor_module.socket = socket

    # Reset the mock
    MockBoto3.lambda_client.invoked = False

    # This should return error
    result = monitor_module.lambda_handler({}, MockContext())

    assert result["statusCode"] == 500
    body = json.loads(result["body"])
    assert "failed to forward" in body["message"].lower()

    print("✅ TEST PASSED: Properly handles missing environment variable")

    # Restore environment variable
    if original_value:
        os.environ["INVOKE_LAMBDA_NAME"] = original_value


def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("LAMBDA DOMAIN MONITOR - TEST SUITE")
    print("=" * 60)

    try:
        test_successful_domain_check()
        test_domain_failure()
        test_missing_environment_variable()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✅")
        print("=" * 60)
        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
