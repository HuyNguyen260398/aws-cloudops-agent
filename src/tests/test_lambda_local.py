#!/usr/bin/env python3
"""
Local testing script for Lambda ping monitor function
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
os.environ["EXECUTION_LAMBDA_ARN"] = (
    "arn:aws:lambda:ap-southeast-1:010382427026:function:execute-remediation"  # Lambda function to execute suggestions
)

# Import the lambda function
from ops.lambda_ping_monitor import lambda_handler


def load_sample_agent_response():
    """Load sample agent response from agent_response.txt"""
    agent_response_path = os.path.join(os.path.dirname(__file__), "agent_response.txt")
    try:
        with open(agent_response_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not load agent_response.txt: {e}")
        return None


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


def test_lambda(use_sample_response=False):
    """Test the Lambda function locally"""
    print("=" * 60)
    print("Testing Lambda Ping Monitor Function Locally")
    if use_sample_response:
        print("(Using sample agent response from agent_response.txt)")
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
    print(f"  Using Sample Response: {use_sample_response}")
    print()

    print("Invoking Lambda function...")
    print("-" * 60)

    try:
        if use_sample_response:
            # Mock the invoke_agent_for_analysis function to return sample response
            sample_response = load_sample_agent_response()
            if sample_response:
                print("Loaded sample agent response from agent_response.txt")
                from src.ops import lambda_ping_monitor

                with patch.object(
                    lambda_ping_monitor,
                    "invoke_agent_for_analysis",
                    return_value=sample_response,
                ):
                    result = lambda_handler(event, context)
            else:
                print("Failed to load sample response, proceeding without mocking")
                result = lambda_handler(event, context)
        else:
            result = lambda_handler(event, context)

        # print("-" * 60)
        # print()
        # print("Lambda Response:")
        # print(json.dumps(result, indent=2))
        # print()

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
    parser.add_argument(
        "--use-sample",
        action="store_true",
        help="Use sample agent response from agent_response.txt instead of invoking cloud agent",
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

    test_lambda(use_sample_response=args.use_sample)
