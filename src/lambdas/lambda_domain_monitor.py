"""
Lambda Function: Domain Monitor
Monitors domain availability and forwards issues to the invoke handler for analysis
"""

import os
import json
import socket
import uuid
import boto3
from datetime import datetime


def invoke_lambda_handler(event_data):
    """Invoke the lambda_invoke_handler with issue details"""
    invoke_lambda_name = os.environ.get("INVOKE_LAMBDA_NAME", "aws-cloudops-invoke-handler")

    if not invoke_lambda_name:
        print("ERROR: INVOKE_LAMBDA_NAME environment variable not set")
        return False

    try:
        lambda_client = boto3.client("lambda")

        print(f"Invoking {invoke_lambda_name} with event data...")
        print(f"Event: {json.dumps(event_data, indent=2)}")

        response = lambda_client.invoke(
            FunctionName=invoke_lambda_name,
            InvocationType="Event",  # Asynchronous invocation
            Payload=json.dumps(event_data),
        )

        if response["StatusCode"] in [200, 202]:
            print(f"✅ Successfully invoked {invoke_lambda_name}")
            return True
        else:
            print(f"❌ Failed to invoke Lambda: Status {response['StatusCode']}")
            return False

    except Exception as e:
        print(f"❌ Error invoking Lambda handler: {e}")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler for domain monitoring
    Detects domain issues and forwards to invoke handler for analysis
    """
    # Domain to monitor (can be configured via environment variable)
    domain = os.environ.get("DOMAIN_TO_MONITOR", "nghuy.link")
    timestamp = datetime.now().isoformat()

    try:
        # Test DNS resolution and connectivity
        socket.gethostbyname(domain)
        print(f"✅ {domain} is reachable at {timestamp}")

        # Uncomment below line for testing
        # raise Exception("Simulated unreachable domain for testing purposes")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"{domain} is healthy",
                    "domain": domain,
                    "timestamp": timestamp,
                }
            ),
        }

    except (socket.gaierror, Exception) as e:
        # Domain unreachable - forward to invoke handler
        error_details = str(e)
        message = f"ALERT: {domain} is unreachable at {timestamp}"
        print(f"⚠️ {message}")
        print(f"Error: {error_details}")

        # Prepare event data for invoke handler
        event_data = {
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
                "timestamp": timestamp,
                "lambda_function": context.function_name if context else "unknown",
                "request_id": context.request_id if context else "unknown",
            },
        }

        # Invoke the lambda_invoke_handler
        invoke_success = invoke_lambda_handler(event_data)

        if invoke_success:
            print(f"✅ Issue forwarded to invoke handler for analysis")
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Issue detected and forwarded for analysis",
                        "domain": domain,
                        "error": error_details,
                        "timestamp": timestamp,
                    }
                ),
            }
        else:
            print(f"❌ Failed to forward issue to invoke handler")
            return {
                "statusCode": 500,
                "body": json.dumps(
                    {
                        "message": "Issue detected but failed to forward for analysis",
                        "domain": domain,
                        "error": error_details,
                        "timestamp": timestamp,
                    }
                ),
            }
