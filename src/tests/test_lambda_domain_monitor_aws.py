"""
Simple test script to invoke the deployed lambda_domain_monitor on AWS
"""

import json
import boto3
import requests
from datetime import datetime


def ping_domain(domain, timeout=5):
    """
    Check if domain is reachable via HTTP/HTTPS
    Returns: (is_reachable, status_code, error_message)
    """
    print(f"\n🔍 Checking domain: {domain}")

    # Try HTTPS first, then HTTP
    for protocol in ["https", "http"]:
        url = f"{protocol}://{domain}"
        try:
            print(f"  Trying {url}...")
            response = requests.get(url, timeout=timeout, allow_redirects=True)
            print(f"  ✅ Domain is reachable - Status: {response.status_code}")
            return True, response.status_code, None
        except requests.exceptions.SSLError as e:
            print(f"  ⚠️  SSL Error: {e}")
            continue
        except requests.exceptions.ConnectionError as e:
            print(f"  ⚠️  Connection Error: {e}")
            continue
        except requests.exceptions.Timeout as e:
            print(f"  ⚠️  Timeout: {e}")
            continue
        except requests.exceptions.RequestException as e:
            print(f"  ⚠️  Request Error: {e}")
            continue

    error_msg = f"Domain {domain} is unreachable via HTTP/HTTPS"
    print(f"  ❌ {error_msg}")
    return False, None, error_msg


def invoke_lambda(domain, error_details):
    """Invoke the deployed Lambda function and display the response"""

    lambda_name = "central_lambda_invoke_handler"
    region = "ap-southeast-2"

    # Sample payload based on lambda_invoke_handler expected event structure
    payload = {
        "service_name": domain,
        "service_type": "Domain/Website",
        "error_details": error_details,
        "issue_type": "domain_unreachable",
        "severity": "critical",
        "status": "DOWN",
        "context": {
            "aws_services": [
                "Amazon Route 53",
                "Amazon CloudFront",
                "AWS Certificate Manager (ACM)",
                "Amazon S3",
                "AWS WAF",
            ],
            "infrastructure_info": f"Domain {domain} is hosted on AWS using Route 53 for DNS, CloudFront as CDN, S3 for static hosting, and ACM for SSL/TLS certificates.",
            "monitoring_source": "lambda_domain_monitor",
            "detection_method": "DNS resolution check",
        },
        "metadata": {
            "domain": domain,
            "timestamp": datetime.now().isoformat(),
            "lambda_function": "aws-cloudops-domain-monitor",
            "request_id": f"test-request-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        },
    }

    print(f"\n🚀 Invoking Lambda: {lambda_name}")
    print(f"Region: {region}")

    try:
        # Configure boto3 client with no retries to ensure single invocation
        from botocore.config import Config

        config = Config(retries={"max_attempts": 1, "mode": "standard"})
        lambda_client = boto3.client("lambda", region_name=region, config=config)

        # Invoke the Lambda function
        response = lambda_client.invoke(
            FunctionName=lambda_name,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        print("Response:")
        print(f"\nStatus Code: {response['StatusCode']}")

    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"❌ Lambda function '{lambda_name}' not found")
        print("Please deploy the function first")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Domain to test
    domain = "nghuy.link"

    # First, try to ping the domain
    is_reachable, status_code, error_msg = ping_domain(domain)

    if is_reachable:
        print(f"\n✅ Domain {domain} is UP and reachable (Status: {status_code})")
        print("No need to invoke Lambda function.\n")
    else:
        print(f"\n❌ Domain {domain} is DOWN")
        print("Proceeding to invoke Lambda function...")
        invoke_lambda(domain, error_msg or "Domain unreachable")
