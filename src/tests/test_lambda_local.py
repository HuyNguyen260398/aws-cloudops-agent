#!/usr/bin/env python3
"""
Local testing script for Lambda Invoke Handler function
Tests general AWS service analysis with mock service events
"""

import sys
import os
import json
from unittest.mock import patch

# Add project root to path
src_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(src_root)

# Set environment variables for testing
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:ap-southeast-1:010382427026:domain-alerts"
os.environ["TEAMS_WEBHOOK_URL"] = (
    "https://bosch.webhook.office.com/webhookb2/88068855-0aad-4ebc-bd2b-a96866c0fe4d@0ae51e19-07c8-4e4b-bb6d-648ee58410f4/IncomingWebhook/bad03592b02c40e7a5eae7b607a181cb/c92e3493-8f7d-44a8-9f87-35b1ecd5178e/V2iasvdXoAsv_QViNlkv2tfJX44vrAA9Eih-oGIqZwES81"  # Add your Teams webhook URL here for testing
)
os.environ["SLACK_WEBHOOK_URL"] = ""
os.environ["AGENT_RUNTIME_ARN"] = (
    "arn:aws:bedrock-agentcore:ap-southeast-1:010382427026:runtime/aws_cloudops_agent-t6rEDA5h0K"
)
os.environ["COGNITO_USERNAME"] = "ted8hc"
os.environ["COGNITO_PASSWORD"] = ""
os.environ["COGNITO_CLIENT_ID"] = "40ede8sr0l0bs37hps0lbgvr8p"
os.environ["AWS_REGION"] = "ap-southeast-1"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-1"
os.environ["S3_ANALYSIS_BUCKET"] = (
    "domain-alert-analysis"  # S3 bucket for storing full analysis reports
)
os.environ["DYNAMODB_ALERTS_TABLE"] = "alerts"  # DynamoDB table for alert tracking
os.environ["APPROVAL_API_URL"] = (
    "https://api.example.com/approval"  # API Gateway URL for approval workflow
)

# Import the lambda function
from lambdas.lambda_invoke_handler import lambda_handler


def load_sample_agent_response():
    """Load sample agent response from assets/samples/agent_response.txt"""
    # Navigate from src/tests/ to project root, then to assets/samples/
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    agent_response_path = os.path.join(
        project_root, "assets", "samples", "agent_response.txt"
    )
    try:
        with open(agent_response_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(
            f"Warning: Could not load agent_response.txt from {agent_response_path}: {e}"
        )
        return None


class MockContext:
    """Mock Lambda context object"""

    def __init__(self):
        self.function_name = "lambda-invoke-handler-local"
        self.function_version = "$LATEST"
        self.invoked_function_arn = (
            "arn:aws:lambda:local:000000000000:function:lambda-invoke-handler-local"
        )
        self.memory_limit_in_mb = 512
        self.aws_request_id = "local-test-request-id"
        self.log_group_name = "/aws/lambda/lambda-invoke-handler-local"
        self.log_stream_name = "2025/12/02/[$LATEST]local"

    def get_remaining_time_in_millis(self):
        return 90000


def get_sample_events():
    """Return sample events for different AWS service types"""
    return {
        "route53": {
            "service_name": "nghuy.link",
            "service_type": "Route53",
            "error_details": "DNS resolution failure - [Errno 11001] getaddrinfo failed",
            "issue_type": "dns_failure",
            "severity": "critical",
            "status": "DOWN",
            "context": {
                "aws_services": [
                    "Amazon Route 53 for DNS management",
                    "Amazon CloudFront as CDN",
                    "AWS Certificate Manager (ACM) for SSL/TLS certificates",
                    "Amazon S3 for static website hosting",
                    "AWS WAF for web application security",
                ],
                "additional_info": "Domain hosted zone: Z1234567890ABC",
            },
            "metadata": {"hosted_zone_id": "Z1234567890ABC", "region": "us-east-1"},
        },
        "cloudfront": {
            "service_name": "E1234567890ABC",
            "service_type": "CloudFront",
            "error_details": "Distribution returning 503 Service Unavailable errors",
            "issue_type": "distribution_error",
            "severity": "high",
            "status": "DEGRADED",
            "context": {
                "aws_services": [
                    "Amazon CloudFront (Primary CDN)",
                    "Amazon S3 (Origin bucket)",
                    "AWS WAF (Web Application Firewall)",
                    "Amazon Route 53 (DNS)",
                ],
                "additional_info": "Distribution ID: E1234567890ABC, Origin: my-bucket.s3.amazonaws.com",
            },
            "metadata": {
                "distribution_id": "E1234567890ABC",
                "origin_bucket": "my-bucket",
            },
        },
        "ec2": {
            "service_name": "i-0123456789abcdef0",
            "service_type": "EC2",
            "error_details": "Instance status checks failing - System reachability check failed",
            "issue_type": "instance_health_check_failure",
            "severity": "critical",
            "status": "IMPAIRED",
            "context": {
                "aws_services": [
                    "Amazon EC2 (Compute instance)",
                    "Amazon VPC (Networking)",
                    "Amazon EBS (Storage volumes)",
                    "AWS Systems Manager (Instance management)",
                ],
                "additional_info": "Instance type: t3.medium, AZ: us-east-1a, VPC: vpc-abc123",
            },
            "metadata": {
                "instance_id": "i-0123456789abcdef0",
                "instance_type": "t3.medium",
                "availability_zone": "us-east-1a",
            },
        },
        "rds": {
            "service_name": "my-production-db",
            "service_type": "RDS",
            "error_details": "Database connection timeout - Unable to connect to RDS instance",
            "issue_type": "connectivity_failure",
            "severity": "critical",
            "status": "UNREACHABLE",
            "context": {
                "aws_services": [
                    "Amazon RDS (MySQL 8.0)",
                    "Amazon VPC (Private subnet)",
                    "AWS Secrets Manager (Credentials)",
                    "Amazon CloudWatch (Monitoring)",
                ],
                "additional_info": "DB instance: my-production-db, Engine: MySQL 8.0.35, Multi-AZ: True",
            },
            "metadata": {
                "db_instance_id": "my-production-db",
                "engine": "mysql",
                "engine_version": "8.0.35",
                "multi_az": True,
            },
        },
        "lambda": {
            "service_name": "data-processing-function",
            "service_type": "Lambda",
            "error_details": "Function invocation errors - Rate exceeded, throttling detected",
            "issue_type": "throttling",
            "severity": "high",
            "status": "THROTTLED",
            "context": {
                "aws_services": [
                    "AWS Lambda (Compute function)",
                    "Amazon DynamoDB (Data storage)",
                    "Amazon SQS (Message queue)",
                    "AWS X-Ray (Tracing)",
                ],
                "additional_info": "Function: data-processing-function, Runtime: Python 3.11, Memory: 1024MB",
            },
            "metadata": {
                "function_name": "data-processing-function",
                "runtime": "python3.11",
                "memory_size": 1024,
            },
        },
    }


def test_lambda(use_sample_response=False, service_type="route53"):
    """Test the Lambda function locally"""
    print("=" * 80)
    print("Testing Lambda Invoke Handler Function Locally")
    print(f"Service Type: {service_type.upper()}")
    if use_sample_response:
        print("(Using sample agent response from agent_response.txt)")
    print("=" * 80)
    print()

    # Get sample event for the specified service type
    sample_events = get_sample_events()
    if service_type not in sample_events:
        print(f"Error: Unknown service type '{service_type}'")
        print(f"Available types: {', '.join(sample_events.keys())}")
        return None

    event = sample_events[service_type]
    context = MockContext()

    print("Test Event:")
    print(json.dumps(event, indent=2))
    print()

    print("Environment Configuration:")
    print(f"  Region: {os.environ.get('AWS_REGION')}")
    print(f"  SNS Topic: {os.environ.get('SNS_TOPIC_ARN')}")
    print(f"  S3 Bucket: {os.environ.get('S3_ANALYSIS_BUCKET')}")
    print(f"  DynamoDB Table: {os.environ.get('DYNAMODB_ALERTS_TABLE')}")
    print(
        f"  Teams Webhook: {'Configured' if os.environ.get('TEAMS_WEBHOOK_URL') else 'Not configured'}"
    )
    print(
        f"  Slack Webhook: {'Configured' if os.environ.get('SLACK_WEBHOOK_URL') else 'Not configured'}"
    )
    print(
        f"  Agent Runtime: {'Configured' if os.environ.get('AGENT_RUNTIME_ARN') else 'Not configured'}"
    )
    print(f"  Using Sample Response: {use_sample_response}")
    print()

    print("Invoking Lambda function...")
    print("-" * 80)

    try:
        if use_sample_response:
            # Mock the invoke_agent_for_analysis function to return sample response
            sample_response = load_sample_agent_response()
            if sample_response:
                print("Loaded sample agent response from agent_response.txt")
                from lambdas import lambda_invoke_handler

                with patch.object(
                    lambda_invoke_handler,
                    "invoke_agent_for_analysis",
                    return_value=(sample_response, "mock-session-id-12345"),
                ):
                    result = lambda_handler(event, context)
            else:
                print("Failed to load sample response, proceeding without mocking")
                result = lambda_handler(event, context)
        else:
            result = lambda_handler(event, context)

        print("-" * 80)
        print()
        print("Lambda Response:")
        print(json.dumps(result, indent=2))
        print()

        response_body = json.loads(result.get("body", "{}"))

        if result["statusCode"] == 200:
            print(f"✓ Analysis completed successfully!")
            print(f"  Alert ID: {response_body.get('alert_id')}")
            print(f"  Severity: {response_body.get('severity')}")
            print(f"  Session ID: {response_body.get('agent_session_id')}")
            if response_body.get("s3_url"):
                print(f"  Full Analysis: {response_body.get('s3_url')}")
        elif result["statusCode"] == 400:
            print(f"✗ Bad Request: {response_body.get('error')}")
        else:
            print(f"✗ Error: {response_body.get('error', 'Unknown error')}")

        print()
        print("=" * 80)
        return result

    except Exception as e:
        print("-" * 80)
        print()
        print(f"✗ Error during execution: {e}")
        print()
        import traceback

        traceback.print_exc()
        print()
        print("=" * 80)
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Test Lambda Invoke Handler locally with various AWS service scenarios"
    )
    parser.add_argument(
        "--service-type",
        "-s",
        choices=["route53", "cloudfront", "ec2", "rds", "lambda"],
        default="route53",
        help="AWS service type to test (default: route53)",
    )
    parser.add_argument("--teams-webhook", help="Microsoft Teams webhook URL")
    parser.add_argument("--slack-webhook", help="Slack webhook URL")
    parser.add_argument("--agent-arn", help="Agent runtime ARN")
    parser.add_argument("--s3-bucket", help="S3 bucket for analysis storage")
    parser.add_argument("--dynamodb-table", help="DynamoDB table for alerts")
    parser.add_argument(
        "--skip-sns",
        action="store_true",
        help="Skip SNS notification (avoid actual email)",
    )
    parser.add_argument(
        "--skip-s3",
        action="store_true",
        help="Skip S3 upload (disable analysis storage)",
    )
    parser.add_argument(
        "--skip-dynamodb",
        action="store_true",
        help="Skip DynamoDB storage (disable alert tracking)",
    )
    parser.add_argument(
        "--use-sample",
        action="store_true",
        help="Use sample agent response from agent_response.txt instead of invoking cloud agent",
    )
    parser.add_argument(
        "--list-services",
        action="store_true",
        help="List available service types and exit",
    )

    args = parser.parse_args()

    # List available services
    if args.list_services:
        print("\nAvailable AWS service types for testing:\n")
        sample_events = get_sample_events()
        for service_type, event in sample_events.items():
            print(
                f"  • {service_type:12} - {event['service_type']}: {event['service_name']}"
            )
            print(f"    {'':12}   Issue: {event['issue_type']}")
            print()
        sys.exit(0)

    # Override environment variables from command line
    if args.teams_webhook:
        os.environ["TEAMS_WEBHOOK_URL"] = args.teams_webhook

    if args.slack_webhook:
        os.environ["SLACK_WEBHOOK_URL"] = args.slack_webhook

    if args.agent_arn:
        os.environ["AGENT_RUNTIME_ARN"] = args.agent_arn

    if args.s3_bucket:
        os.environ["S3_ANALYSIS_BUCKET"] = args.s3_bucket

    if args.dynamodb_table:
        os.environ["DYNAMODB_ALERTS_TABLE"] = args.dynamodb_table

    if args.skip_sns:
        os.environ["SNS_TOPIC_ARN"] = ""
        print("Note: SNS notifications disabled for testing")

    if args.skip_s3:
        os.environ["S3_ANALYSIS_BUCKET"] = ""
        print("Note: S3 upload disabled for testing")

    if args.skip_dynamodb:
        os.environ["DYNAMODB_ALERTS_TABLE"] = ""
        print("Note: DynamoDB storage disabled for testing")

    if args.skip_sns or args.skip_s3 or args.skip_dynamodb:
        print()

    test_lambda(use_sample_response=args.use_sample, service_type=args.service_type)
