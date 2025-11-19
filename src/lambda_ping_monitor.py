import socket
import boto3
import json
import os
import uuid
import requests
import urllib.parse
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def get_cognito_jwt_token(username, password, client_id, region):
    """Get JWT access token from AWS Cognito"""
    cognito_client = boto3.client("cognito-idp", region_name=region)

    try:
        response = cognito_client.initiate_auth(
            ClientId=client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        return response["AuthenticationResult"]["AccessToken"]
    except Exception as e:
        print(f"Error getting Cognito token: {e}")
        return None


def invoke_agent_for_analysis(domain, timestamp, error_details):
    """Invoke AWS CloudOps Agent to analyze domain issue"""
    # Get configuration from environment variables
    runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
    # AWS_REGION is automatically provided by Lambda environment
    region = os.environ.get(
        "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-1")
    )
    cognito_username = os.environ.get("COGNITO_USERNAME")
    cognito_password = os.environ.get("COGNITO_PASSWORD")
    cognito_client_id = os.environ.get("COGNITO_CLIENT_ID")

    if not all([runtime_arn, cognito_username, cognito_password, cognito_client_id]):
        print("Warning: Agent configuration incomplete. Skipping agent analysis.")
        return None

    print("Invoking AWS CloudOps Agent for analysis...")

    try:
        # Get JWT token
        jwt_token = get_cognito_jwt_token(
            cognito_username, cognito_password, cognito_client_id, region
        )

        if not jwt_token:
            print("Failed to obtain JWT token")
            return None

        # Prepare agent invocation
        escaped_agent_arn = urllib.parse.quote(runtime_arn, safe="")
        url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

        session_id = str(uuid.uuid4())

        # Construct analysis prompt
        prompt = f"""URGENT: Domain monitoring alert requires immediate analysis.

Domain: {domain}
Status: UNREACHABLE
Timestamp: {timestamp}
Error: {error_details}

This website is built user following AWS services:
1. Amazon Route 53 for DNS management
2. Amazon CloudFront as the Content Delivery Network (CDN)
3. AWS Certificate Manager (ACM) for SSL/TLS certificates
4. Amazon S3 for static website hosting
5. AWS WAF for web application security

Please perform the following analysis:
1. Check if there are any known AWS service issues affecting network connectivity
2. Verify if there are recent changes to networking configurations or security groups
3. Investigate DNS resolution issues and nameserver status
4. Check for any recent deployments or infrastructure changes
5. Review CloudWatch logs for related errors

Provide a comprehensive summary of your findings and recommended actions to resolve this issue.

IMPORTANT: Start your response with a clear executive summary of the root cause and immediate actions needed."""

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        }

        payload = {
            "prompt": prompt,
            "session_id": session_id,
            "actor_id": cognito_username,
        }

        # Invoke agent with streaming
        response = requests.post(
            url, headers=headers, data=json.dumps(payload), stream=True, timeout=60
        )

        if response.status_code == 200:
            agent_response = ""
            # Collect streaming response
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode("utf-8")
                    if decoded_line.startswith("data: "):
                        data_content = decoded_line[6:]
                        try:
                            data_json = json.loads(data_content)
                            if data_json.get("type") == "text_delta":
                                agent_response += data_json.get("content", "")
                        except json.JSONDecodeError:
                            pass

            # Format the agent response - convert escaped characters to readable format
            formatted_response = (
                agent_response.replace("\\n", "\n")
                .replace("\\ud83d\\udea8", "🚨")
                .replace("\\ud83d\\udccb", "📋")
                .replace("\\ud83d\\udd0d", "🔍")
                .replace("\\u2705", "✅")
                .replace("\\u26a0\\ufe0f", "⚠️")
                .replace("\\u274c", "❌")
                .replace("\\ud83d\\udcca", "📊")
                .replace("\\ud83d\\udd34", "🔴")
                .replace("\\ud83d\\udd27", "🔧")
                .replace("\\u2192", "→")
            )

            print(f"Agent analysis completed ({len(formatted_response)} chars)")
            return formatted_response
        else:
            print(f"Agent invocation failed: {response.status_code}")
            return None

    except requests.exceptions.Timeout:
        print("Agent request timed out")
        return None
    except Exception as e:
        print(f"Error invoking agent: {e}")
        return None


def send_slack_notification(domain, status, timestamp, agent_analysis=None):
    """Send notification to Slack channel via webhook using adaptive card format"""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("SLACK_WEBHOOK_URL environment variable not set")
        return False

    # Create Block Kit message for Slack (similar to adaptive cards)
    color = "#FF0000" if status == "down" else "#00FF00"
    status_prefix = "ALERT" if status == "down" else "OK"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{status_prefix}: Domain Alert - {domain}",
                "emoji": False,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Domain:*\n{domain}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{status.upper()}"},
                {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
            ],
        },
    ]

    # Add agent analysis if available
    if agent_analysis:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*AI Agent Analysis:*\n{agent_analysis[:2800]}",
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "Monitored by AWS Lambda"}],
        }
    )

    message = {
        "blocks": blocks,
        "attachments": [{"color": color, "fallback": f"Domain {domain} is {status}"}],
    }

    try:
        req = Request(
            webhook_url,
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        response = urlopen(req)
        print(f"Slack notification sent: {response.read().decode()}")
        return True
    except HTTPError as e:
        print(f"Failed to send Slack notification - HTTP Error: {e.code} {e.reason}")
        return False
    except URLError as e:
        print(f"Failed to send Slack notification - URL Error: {e.reason}")
        return False
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")
        return False


def send_teams_notification(domain, status, timestamp, agent_analysis=None):
    """Send notification to Microsoft Teams channel via webhook"""
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

    if not webhook_url:
        print("TEAMS_WEBHOOK_URL environment variable not set")
        return False

    # Create message card for Teams
    sections = [
        {
            "activityTitle": f"Domain Alert: {domain}",
            "activitySubtitle": timestamp,
            "facts": [
                {"name": "Domain:", "value": domain},
                {"name": "Status:", "value": status.upper()},
                {"name": "Timestamp:", "value": timestamp},
            ],
            "markdown": True,
        }
    ]

    # Add agent analysis if available
    if agent_analysis:
        sections.append(
            {
                "activityTitle": "AI Agent Analysis",
                "text": agent_analysis[:2800],
                "markdown": True,
            }
        )

    message_card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": "FF0000" if status == "down" else "00FF00",
        "summary": f"Domain Alert: {domain}",
        "sections": sections,
    }

    try:
        req = Request(
            webhook_url,
            data=json.dumps(message_card).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        response = urlopen(req)
        print(f"Teams notification sent: {response.read().decode()}")
        return True
    except HTTPError as e:
        print(f"Failed to send Teams notification - HTTP Error: {e.code} {e.reason}")
        return False
    except URLError as e:
        print(f"Failed to send Teams notification - URL Error: {e.reason}")
        return False
    except Exception as e:
        print(f"Failed to send Teams notification: {e}")
        return False


def lambda_handler(event, context):
    domain = "nghuy.link"
    timestamp = str(datetime.now())

    try:
        # Test DNS resolution and connectivity
        socket.gethostbyname(domain)
        print(f"{domain} is reachable at {timestamp}")
        return {"statusCode": 200, "body": f"{domain} is healthy"}

    except socket.gaierror as e:
        # Domain unreachable - send alerts
        error_details = str(e)
        message = f"ALERT: {domain} is unreachable at {timestamp}"
        print(message)

        # Invoke AI agent for analysis
        agent_analysis = invoke_agent_for_analysis(domain, timestamp, error_details)

        # Send SNS notification
        sns = boto3.client("sns")
        sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

        if sns_topic_arn:
            try:
                email_message = message
                if agent_analysis:
                    email_message += f"\n\nAI Agent Analysis:\n{agent_analysis}"

                sns.publish(
                    TopicArn=sns_topic_arn,
                    Subject=f"Domain Alert: {domain} Down",
                    Message=email_message,
                )
                print("Email alert sent")
            except Exception as e:
                print(f"Failed to send email: {e}")
        else:
            print("SNS_TOPIC_ARN not configured, skipping email notification")

        # Send Teams notification with agent analysis
        send_teams_notification(domain, "down", timestamp, agent_analysis)

        # Send Slack notification with agent analysis
        send_slack_notification(domain, "down", timestamp, agent_analysis)

        return {
            "statusCode": 500,
            "body": message,
            "agent_analysis": agent_analysis if agent_analysis else "Not available",
        }
