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
from decimal import Decimal


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


def extract_executive_summary(agent_analysis):
    """Extract executive summary from agent analysis for Slack preview"""
    if not agent_analysis:
        return None

    # Look for executive summary section
    summary_markers = [
        "EXECUTIVE SUMMARY",
        "ROOT CAUSE",
        "IMMEDIATE ACTIONS",
        "CRITICAL FINDINGS",
    ]

    lines = agent_analysis.split("\n")
    summary_lines = []
    in_summary = False
    section_count = 0

    for line in lines:
        # Check if we hit a summary section
        if any(marker in line.upper() for marker in summary_markers):
            in_summary = True
            section_count += 1
            summary_lines.append(line)
            # Stop after capturing 2-3 key sections
            if section_count >= 3:
                break
            continue

        # If in summary section, keep adding lines
        if in_summary:
            # Stop at next major section or after reasonable length
            if line.startswith("##") and section_count > 1:
                break
            if len("\n".join(summary_lines)) > 1500:
                summary_lines.append("\n_[Summary continues...]_")
                break
            summary_lines.append(line)

    return "\n".join(summary_lines) if summary_lines else agent_analysis[:1500]


def summarize_agent_analysis(agent_analysis):
    """Create a concise summary of agent analysis for Teams notification"""
    if not agent_analysis:
        return "No analysis available"

    summary_parts = []

    # Extract Executive Summary (more generous limit)
    if "EXECUTIVE SUMMARY" in agent_analysis:
        exec_start = agent_analysis.find("EXECUTIVE SUMMARY")
        # Find the end - look for the next major section or separator
        exec_end = agent_analysis.find("\n##", exec_start + 20)
        if exec_end == -1:
            exec_end = agent_analysis.find("---", exec_start + 20)
        if exec_end > exec_start:
            exec_summary = agent_analysis[exec_start:exec_end].strip()
            summary_parts.append(exec_summary[:1000])

    # Extract Root Cause Analysis with CloudTrail findings
    if "ROOT CAUSE" in agent_analysis or "CRITICAL FINDING" in agent_analysis:
        # Find the root cause section
        root_start = max(
            agent_analysis.find("ROOT CAUSE") if "ROOT CAUSE" in agent_analysis else -1,
            (
                agent_analysis.find("CRITICAL FINDING")
                if "CRITICAL FINDING" in agent_analysis
                else -1
            ),
        )

        if root_start > 0:
            # Extract until we hit Critical Findings table or another major section
            root_end = agent_analysis.find("## ", root_start + 20)
            if root_end == -1:
                root_end = agent_analysis.find("\n\n---", root_start + 20)

            if root_end > root_start:
                root_cause = agent_analysis[root_start:root_end].strip()
                # Include more of the root cause analysis
                summary_parts.append("\n\n" + root_cause[:1200])

    # Extract Critical Findings table
    if "CRITICAL FINDINGS" in agent_analysis:
        findings_start = agent_analysis.find("CRITICAL FINDINGS")
        # Find the table - look for the next ## or the end of the table section
        findings_end = agent_analysis.find("\n\n##", findings_start)
        if findings_end == -1:
            findings_end = agent_analysis.find("\n\n---\n\n##", findings_start)
        if findings_end == -1:
            # Try to find end by looking for double line break after table
            table_start = agent_analysis.find("|", findings_start)
            if table_start > 0:
                # Find end of table (last row with |)
                remaining = agent_analysis[table_start:]
                lines = remaining.split("\n")
                table_lines = []
                for line in lines:
                    if "|" in line:
                        table_lines.append(line)
                    elif table_lines:
                        break
                findings_end = table_start + len("\n".join(table_lines))

        if findings_end > findings_start:
            findings = agent_analysis[findings_start:findings_end].strip()
            summary_parts.append("\n\n" + findings)

    # If no sections found, use first part
    if not summary_parts:
        return agent_analysis[:1500] + "\n\n_[Analysis continues...]_"

    summary = "".join(summary_parts)

    # Don't truncate if we're close to the limit - better to show complete sections
    if len(summary) > 2500:
        # Find a good breaking point (end of a paragraph or section)
        truncate_at = summary.rfind("\n\n", 0, 2400)
        if truncate_at > 1500:
            summary = (
                summary[:truncate_at]
                + "\n\n_[Analysis continues... View full report for complete details]_"
            )
        else:
            summary = summary[:2400] + "\n\n_[Analysis continues...]_"

    return summary


def upload_analysis_to_s3(alert_id, domain, timestamp, agent_analysis):
    """Upload full analysis to S3 bucket and return the URL"""
    s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET")

    if not s3_bucket:
        print("S3_ANALYSIS_BUCKET environment variable not set")
        return None

    try:
        s3_client = boto3.client("s3")
        region = os.environ.get("AWS_REGION", "ap-southeast-1")

        # Create filename with timestamp
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        filename = f"alerts/{date_str}/{domain}/{time_str}-{alert_id}.md"

        # Format analysis as markdown
        markdown_content = f"""# Domain Alert Analysis Report

**Alert ID:** {alert_id}  
**Domain:** {domain}  
**Timestamp:** {timestamp}  
**Status:** UNREACHABLE

---

{agent_analysis}

---

*Generated by AWS CloudOps Agent*  
*Report ID: {alert_id}*
"""

        # Upload to S3
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=filename,
            Body=markdown_content.encode("utf-8"),
            ContentType="text/markdown",
            Metadata={
                "alert-id": alert_id,
                "domain": domain,
                "timestamp": timestamp,
            },
        )

        # Generate URL
        s3_url = f"https://{s3_bucket}.s3.{region}.amazonaws.com/{filename}"
        print(f"Analysis uploaded to S3: {s3_url}")

        return s3_url

    except Exception as e:
        print(f"Failed to upload analysis to S3: {e}")
        return None


def store_alert_data(
    alert_id, domain, status, timestamp, error_details, agent_analysis
):
    """Store alert data in DynamoDB for approval workflow"""
    dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")

    if not dynamodb_table:
        print("DYNAMODB_ALERTS_TABLE environment variable not set")
        return False

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(dynamodb_table)

        table.put_item(
            Item={
                "alert_id": alert_id,
                "domain": domain,
                "status": status,
                "timestamp": timestamp,
                "error_details": error_details,
                "agent_analysis": agent_analysis if agent_analysis else "N/A",
                "approval_status": "pending",
                "ttl": int(datetime.now().timestamp()) + 86400,  # Expire after 24 hours
            }
        )
        print(f"Alert data stored in DynamoDB with ID: {alert_id}")
        print(
            f"Full analysis length: {len(agent_analysis) if agent_analysis else 0} characters"
        )
        return True
    except Exception as e:
        print(f"Failed to store alert data in DynamoDB: {e}")
        return False


def send_slack_notification(
    domain, status, timestamp, agent_analysis=None, alert_id=None
):
    """Send notification to Slack channel via webhook using adaptive card format with approval button"""
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
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Domain:*\n{domain}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{status.upper()}"},
                {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
                {"type": "mrkdwn", "text": f"*Alert ID:*\n`{alert_id}`"},
            ],
        },
    ]

    # Add agent analysis if available
    if agent_analysis:
        blocks.append({"type": "divider"})

        # Extract executive summary for preview
        summary_text = extract_executive_summary(agent_analysis)
        full_length = len(agent_analysis)

        # If analysis is very long, show summary + link to full version
        if full_length > 2000:
            # Limit summary to 1800 chars to leave room for other content
            if len(summary_text) > 1800:
                summary_text = summary_text[:1800]

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🤖 AI Agent Analysis (Summary):*\n{summary_text}",
                    },
                }
            )

            # Add context showing full analysis is available
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"📄 Full analysis: {full_length:,} characters | Complete details stored in DynamoDB",
                        }
                    ],
                }
            )
        else:
            # For shorter analysis, show it all
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*🤖 AI Agent Analysis:*\n{agent_analysis}",
                    },
                }
            )

        # Add approval button only if status is down and agent analysis is available
        if status == "down":
            blocks.append({"type": "divider"})
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Review the agent's analysis and approve to execute remediation actions:*",
                    },
                }
            )

            # Add buttons for actions
            action_elements = [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve & Execute",
                        "emoji": True,
                    },
                    "style": "primary",
                    "value": alert_id,
                    "action_id": f"approve_remediation_{alert_id}",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Dismiss",
                        "emoji": True,
                    },
                    "style": "danger",
                    "value": alert_id,
                    "action_id": f"dismiss_alert_{alert_id}",
                },
            ]

            # Add "View Full Analysis" button if analysis was truncated
            if full_length > 2000:
                action_elements.append(
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "📄 View Full Analysis",
                            "emoji": True,
                        },
                        "value": alert_id,
                        "action_id": f"view_full_analysis_{alert_id}",
                    }
                )

            blocks.append(
                {
                    "type": "actions",
                    "elements": action_elements,
                }
            )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "🔍 Monitored by AWS Lambda | Powered by AI CloudOps Agent",
                }
            ],
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


def send_teams_notification(
    domain, status, timestamp, agent_analysis=None, alert_id=None, s3_url=None
):
    """Send notification to Microsoft Teams channel via webhook using Adaptive Cards"""
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

    if not webhook_url:
        print("TEAMS_WEBHOOK_URL environment variable not set")
        return False

    # Determine color and icon based on status
    color = "Attention" if status == "down" else "Good"
    icon = "⚠️" if status == "down" else "✅"

    # Create summary from analysis
    summary_text = (
        summarize_agent_analysis(agent_analysis)
        if agent_analysis
        else "No analysis available"
    )

    # Build Adaptive Card
    card_body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": f"{icon} Domain Alert: {domain}",
            "wrap": True,
            "color": color,
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Domain:", "value": domain},
                {"title": "Status:", "value": status.upper()},
                {"title": "Timestamp:", "value": timestamp},
                {"title": "Alert ID:", "value": alert_id if alert_id else "N/A"},
            ],
        },
    ]

    # Add analysis summary if available
    if agent_analysis:
        card_body.extend(
            [
                {"type": "TextBlock", "text": "---", "separator": True},
                {
                    "type": "TextBlock",
                    "size": "Medium",
                    "weight": "Bolder",
                    "text": "🤖 AI Agent Analysis Summary",
                    "wrap": True,
                },
                {
                    "type": "TextBlock",
                    "text": summary_text,
                    "wrap": True,
                    "separator": True,
                },
            ]
        )

    # Add action buttons
    actions = []

    if status == "down" and alert_id:
        # Get Lambda function ARN for execution
        execution_lambda_arn = os.environ.get("EXECUTION_LAMBDA_ARN")

        # Execute Suggestions button (triggers Lambda function)
        if execution_lambda_arn:
            # Extract function name from ARN
            function_name = execution_lambda_arn.split(":")[-1]
            region = os.environ.get("AWS_REGION", "ap-southeast-1")
            lambda_url = f"https://console.aws.amazon.com/lambda/home?region={region}#/functions/{function_name}"

            actions.append(
                {
                    "type": "Action.OpenUrl",
                    "title": "🚀 Execute Suggestions",
                    "url": lambda_url,
                    "style": "positive",
                }
            )

        # View Detail Analysis button
        if s3_url:
            actions.append(
                {
                    "type": "Action.OpenUrl",
                    "title": "📄 View Detail Analysis",
                    "url": s3_url,
                }
            )

    # Add actions to card if any
    if actions:
        card_body.append({"type": "TextBlock", "text": "---", "separator": True})

    # Create the adaptive card message
    adaptive_card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": card_body,
                    "actions": actions if actions else [],
                    "msteams": {"width": "Full"},
                },
            }
        ],
    }

    try:
        req = Request(
            webhook_url,
            data=json.dumps(adaptive_card).encode("utf-8"),
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
        raise Exception("Simulated unreachable domain for testing purposes")
        return {"statusCode": 200, "body": f"{domain} is healthy"}

    # except socket.gaierror as e:
    except Exception as e:
        # Domain unreachable - send alerts
        error_details = str(e)
        message = f"ALERT: {domain} is unreachable at {timestamp}"
        print(message)

        # Generate unique alert ID
        alert_id = str(uuid.uuid4())

        # Invoke AI agent for analysis
        # agent_analysis = invoke_agent_for_analysis(domain, timestamp, error_details)
        # Read sample agent analysis from file for testing
        try:
            with open("agent_response.txt", "r", encoding="utf-8") as f:
                agent_analysis = f.read()
        except FileNotFoundError:
            agent_analysis = "Simulated agent analysis for testing purposes."
        except Exception as e:
            print(f"Error reading agent_response.txt: {e}")
            agent_analysis = "Simulated agent analysis for testing purposes."

        # Upload full analysis to S3
        s3_url = None
        if agent_analysis:
            s3_url = upload_analysis_to_s3(alert_id, domain, timestamp, agent_analysis)

        # Store alert data in DynamoDB for approval workflow
        # store_alert_data(
        #     alert_id, domain, "down", timestamp, error_details, agent_analysis
        # )

        # Send SNS notification
        sns = boto3.client("sns")
        sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

        if sns_topic_arn:
            try:
                email_message = message
                if agent_analysis:
                    summary = summarize_agent_analysis(agent_analysis)
                    email_message += f"\n\nAI Agent Analysis Summary:\n{summary}"
                    if s3_url:
                        email_message += f"\n\nFull Analysis: {s3_url}"
                    email_message += f"\n\nAlert ID: {alert_id}"

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

        # Send Teams notification with agent analysis (Adaptive Card with buttons)
        send_teams_notification(
            domain, "down", timestamp, agent_analysis, alert_id, s3_url
        )

        # Send Slack notification with agent analysis and approval button
        send_slack_notification(domain, "down", timestamp, agent_analysis, alert_id)

        return {
            "statusCode": 500,
            "body": message,
            "alert_id": alert_id,
            "agent_analysis": agent_analysis if agent_analysis else "Not available",
        }
