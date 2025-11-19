#!/usr/bin/env python3
"""
Local testing script for Lambda ping monitor function
"""

import sys
import os
import json

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Set environment variables for testing
os.environ["SNS_TOPIC_ARN"] = "arn:aws:sns:ap-southeast-1:010382427026:domain-alerts"
os.environ["TEAMS_WEBHOOK_URL"] = ""  # Add your Teams webhook URL here for testing
os.environ["SLACK_WEBHOOK_URL"] = ""
os.environ["AGENT_RUNTIME_ARN"] = ""
os.environ["COGNITO_USERNAME"] = "ted8hc"
os.environ["COGNITO_PASSWORD"] = ""
os.environ["COGNITO_CLIENT_ID"] = "40ede8sr0l0bs37hps0lbgvr8p"
os.environ["AWS_REGION"] = "ap-southeast-1"
os.environ["AWS_DEFAULT_REGION"] = "ap-southeast-1"

# Import the lambda function
from src.lambda_ping_monitor import lambda_handler


class MockContext:
    """Mock Lambda context object"""

    def __init__(self):
        self.function_name = "domain-ping-monitor-local"
        self.function_version = "$LATEST"
        self.invoked_function_arn = (
            "arn:aws:lambda:local:000000000000:function:domain-ping-monitor-local"
        )
        self.memory_limit_in_mb = 256
        self.aws_request_id = "local-test-request-id"
        self.log_group_name = "/aws/lambda/domain-ping-monitor-local"
        self.log_stream_name = "2025/11/19/[$LATEST]local"

    def get_remaining_time_in_millis(self):
        return 90000


def test_lambda():
    """Test the Lambda function locally"""
    print("=" * 60)
    print("Testing Lambda Ping Monitor Function Locally")
    print("=" * 60)
    print()

    # Create mock event and context
    event = {}
    context = MockContext()

    print("Environment Configuration:")
    print(f"  Region: {os.environ.get('AWS_REGION')}")
    print(f"  SNS Topic: {os.environ.get('SNS_TOPIC_ARN')}")
    print(
        f"  Teams Webhook: {'Configured' if os.environ.get('TEAMS_WEBHOOK_URL') else 'Not configured'}"
    )
    print(
        f"  Slack Webhook: {'Configured' if os.environ.get('SLACK_WEBHOOK_URL') else 'Not configured'}"
    )
    print(
        f"  Agent Runtime: {'Configured' if os.environ.get('AGENT_RUNTIME_ARN') else 'Not configured'}"
    )
    print()

    print("Invoking Lambda function...")
    print("-" * 60)

    try:
        result = lambda_handler(event, context)

        print("-" * 60)
        print()
        print("Lambda Response:")
        print(json.dumps(result, indent=2))
        print()

        if result["statusCode"] == 200:
            print("✓ Domain is healthy!")
        else:
            print("✗ Domain is unreachable - alerts sent")

        print()
        print("=" * 60)
        return result

    except Exception as e:
        print("-" * 60)
        print()
        print(f"✗ Error during execution: {e}")
        print()
        import traceback

        traceback.print_exc()
        print()
        print("=" * 60)
        return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Lambda ping monitor locally")
    parser.add_argument("--teams-webhook", help="Microsoft Teams webhook URL")
    parser.add_argument("--slack-webhook", help="Slack webhook URL")
    parser.add_argument("--agent-arn", help="Agent runtime ARN")
    parser.add_argument(
        "--skip-sns",
        action="store_true",
        help="Skip SNS notification (avoid actual email)",
    )

    args = parser.parse_args()

    # Override environment variables from command line
    if args.teams_webhook:
        os.environ["TEAMS_WEBHOOK_URL"] = args.teams_webhook

    if args.slack_webhook:
        os.environ["SLACK_WEBHOOK_URL"] = args.slack_webhook

    if args.agent_arn:
        os.environ["AGENT_RUNTIME_ARN"] = args.agent_arn

    if args.skip_sns:
        os.environ["SNS_TOPIC_ARN"] = ""
        print("Note: SNS notifications disabled for testing")
        print()

    test_lambda()
