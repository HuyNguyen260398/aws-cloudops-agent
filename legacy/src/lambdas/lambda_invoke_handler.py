"""
Lambda Function: General AWS Service Analysis Handler
Receives service issue details from upstream monitors and invokes AI agent for analysis
Supports multiple AWS services: Route53, CloudFront, S3, EC2, RDS, Lambda, etc.
"""

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


def construct_analysis_prompt(service_name, timestamp, error_details, context=None):
    """
    Create comprehensive analysis prompt with structured output requirements
    Supports any AWS service with dynamic context
    """
    # Build infrastructure context from provided details
    infrastructure_context = ""
    if context:
        if isinstance(context, dict):
            if context.get("aws_services"):
                infrastructure_context = "\n\n**Infrastructure Context:**\n"
                for idx, service in enumerate(context["aws_services"], 1):
                    infrastructure_context += f"{idx}. {service}\n"

            if context.get("additional_info"):
                infrastructure_context += (
                    f"\n**Additional Information:**\n{context['additional_info']}\n"
                )
        elif isinstance(context, str):
            infrastructure_context = f"\n\n**Infrastructure Context:**\n{context}\n"

    prompt = f"""URGENT: AWS Service monitoring alert requires immediate analysis.

**Incident Details:**
- Service/Resource: {service_name}
- Status: ISSUE DETECTED
- Timestamp: {timestamp}
- Error: {error_details}{infrastructure_context}

**Analysis Requirements:**

1. **Executive Summary** (First 200 words)
   - Root cause in one sentence
   - Immediate impact assessment
   - Estimated time to resolve

2. **Detailed Investigation**
   - Check AWS service health status
   - Verify Route 53 DNS records and hosted zones
   - Validate CloudFront distribution configuration
   - Review ACM certificate status
   - Check S3 bucket configuration and permissions
   - Analyze CloudTrail for recent changes
   - Review CloudWatch logs and metrics

3. **Root Cause Analysis**
   - Primary issue identification
   - Contributing factors
   - Timeline of events

4. **Critical Findings** (Table format)
   - Component status (OK/WARNING/CRITICAL)
   - Specific issues found

5. **Immediate Actions Required** (Numbered list)
   - Specific AWS CLI/SDK commands to execute
   - Order of execution (dependencies)
   - Expected outcome for each action
   - Rollback steps if needed

6. **Prevention Recommendations**
   - Long-term fixes
   - Monitoring improvements
   - Architecture changes

**Output Format:** Use markdown with clear sections and tables.
**CRITICAL:** Ensure "IMMEDIATE ACTIONS REQUIRED" section contains executable steps with specific AWS API calls.
"""
    return prompt


def invoke_agent_for_analysis(
    service_name, timestamp, error_details, context=None, session_id=None
):
    """Invoke AWS CloudOps Agent to analyze any AWS service issue"""
    runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
    region = os.environ.get(
        "AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-southeast-1")
    )
    cognito_username = os.environ.get("COGNITO_USERNAME")
    cognito_password = os.environ.get("COGNITO_PASSWORD")
    cognito_client_id = os.environ.get("COGNITO_CLIENT_ID")

    if not all([runtime_arn, cognito_username, cognito_password, cognito_client_id]):
        print("Warning: Agent configuration incomplete. Skipping agent analysis.")
        return None, None

    print(f"Invoking AWS CloudOps Agent for {service_name} analysis...")

    try:
        # Get JWT token
        jwt_token = get_cognito_jwt_token(
            cognito_username, cognito_password, cognito_client_id, region
        )

        if not jwt_token:
            print("Failed to obtain JWT token")
            return None, None

        # Prepare agent invocation
        escaped_agent_arn = urllib.parse.quote(runtime_arn, safe="")
        url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

        # Create or use provided session ID
        if not session_id:
            session_id = str(uuid.uuid4())

        # Construct enhanced analysis prompt with context
        prompt = construct_analysis_prompt(
            service_name, timestamp, error_details, context
        )

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
            url, headers=headers, data=json.dumps(payload), stream=True, timeout=90
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
            return formatted_response, session_id
        else:
            print(f"Agent invocation failed: {response.status_code}")
            return None, None

    except requests.exceptions.Timeout:
        print("Agent request timed out")
        return None, None
    except Exception as e:
        print(f"Error invoking agent: {e}")
        return None, None


def summarize_agent_analysis(agent_analysis):
    """Create a concise summary of agent analysis for notifications"""
    if not agent_analysis:
        return "No analysis available"

    summary_parts = []

    # Extract Executive Summary
    if "EXECUTIVE SUMMARY" in agent_analysis or "Executive Summary" in agent_analysis:
        exec_start = agent_analysis.find("EXECUTIVE SUMMARY")
        if exec_start == -1:
            exec_start = agent_analysis.find("Executive Summary")
        exec_end = agent_analysis.find("\n##", exec_start + 20)
        if exec_end == -1:
            exec_end = agent_analysis.find("---", exec_start + 20)
        if exec_end > exec_start:
            exec_summary = agent_analysis[exec_start:exec_end].strip()
            summary_parts.append(exec_summary[:1000])

    # Extract Root Cause
    if "ROOT CAUSE" in agent_analysis or "Root Cause" in agent_analysis:
        root_start = max(
            agent_analysis.find("ROOT CAUSE") if "ROOT CAUSE" in agent_analysis else -1,
            agent_analysis.find("Root Cause") if "Root Cause" in agent_analysis else -1,
        )

        if root_start > 0:
            root_end = agent_analysis.find("## ", root_start + 20)
            if root_end == -1:
                root_end = agent_analysis.find("\n\n---", root_start + 20)

            if root_end > root_start:
                root_cause = agent_analysis[root_start:root_end].strip()
                summary_parts.append("\n\n" + root_cause[:1200])

    # Extract Critical Findings
    if "CRITICAL FINDINGS" in agent_analysis or "Critical Findings" in agent_analysis:
        findings_start = max(
            agent_analysis.find("CRITICAL FINDINGS"),
            agent_analysis.find("Critical Findings"),
        )
        findings_end = agent_analysis.find("\n\n##", findings_start)
        if findings_end == -1:
            table_start = agent_analysis.find("|", findings_start)
            if table_start > 0:
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

    if not summary_parts:
        return agent_analysis[:1500] + "\n\n_[Analysis continues...]_"

    summary = "".join(summary_parts)

    if len(summary) > 2500:
        truncate_at = summary.rfind("\n\n", 0, 2400)
        if truncate_at > 1500:
            summary = (
                summary[:truncate_at]
                + "\n\n_[Analysis continues... View full report for complete details]_"
            )
        else:
            summary = summary[:2400] + "\n\n_[Analysis continues...]_"

    return summary


def upload_analysis_to_s3(
    alert_id, service_name, timestamp, agent_analysis, service_type="general"
):
    """Upload full analysis to S3 bucket and return the URL"""
    s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET")

    if not s3_bucket:
        print("S3_ANALYSIS_BUCKET environment variable not set")
        return None, None

    try:
        s3_client = boto3.client("s3")
        region = os.environ.get("AWS_REGION", "ap-southeast-1")

        # Create filename with timestamp and service type
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        # Sanitize service_name for use in path
        safe_service_name = (
            service_name.replace("/", "-").replace(":", "-").replace(" ", "-")
        )
        filename = f"alerts/{date_str}/{service_type}/{safe_service_name}/{time_str}-{alert_id}.md"

        # Format analysis as markdown
        markdown_content = f"""# AWS Service Analysis Report

**Alert ID:** {alert_id}  
**Service/Resource:** {service_name}  
**Service Type:** {service_type}  
**Timestamp:** {timestamp}  
**Status:** ISSUE DETECTED

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
                "service-name": safe_service_name,
                "service-type": service_type,
                "timestamp": timestamp,
            },
        )

        # Generate URL
        s3_url = f"https://{s3_bucket}.s3.{region}.amazonaws.com/{filename}"
        print(f"Analysis uploaded to S3: {s3_url}")

        return s3_url, filename

    except Exception as e:
        print(f"Failed to upload analysis to S3: {e}")
        return None, None


def store_alert_in_dynamodb(
    alert_id,
    service_name,
    timestamp,
    error_details,
    agent_analysis,
    agent_session_id,
    s3_url,
    s3_key,
    service_type="general",
    issue_type="service_issue",
    severity="high",
    additional_metadata=None,
):
    """Store alert metadata in DynamoDB for workflow tracking"""
    dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")

    if not dynamodb_table:
        print("DYNAMODB_ALERTS_TABLE environment variable not set")
        return False

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(dynamodb_table)

        # Build DynamoDB item
        item = {
            "alert_id": alert_id,
            "timestamp": timestamp,
            "service_name": service_name,
            "service_type": service_type,
            "issue_type": issue_type,
            "error_details": error_details,
            "agent_session_id": agent_session_id,
            "agent_analysis": summarize_agent_analysis(agent_analysis)[:1000],
            "s3_analysis_url": s3_url,
            "s3_analysis_key": s3_key,
            "approval_status": "pending",
            "execution_status": "not_started",
            "severity": severity,
            "ttl": int(datetime.now().timestamp()) + (7 * 86400),  # 7 days
        }

        # Add any additional metadata from upstream
        if additional_metadata and isinstance(additional_metadata, dict):
            for key, value in additional_metadata.items():
                if key not in item:  # Don't override core fields
                    item[key] = value

        table.put_item(Item=item)
        print(f"Alert {alert_id} stored in DynamoDB")
        return True
    except Exception as e:
        print(f"Failed to store alert in DynamoDB: {e}")
        return False


def send_sns_notification(
    service_name,
    timestamp,
    alert_id,
    agent_analysis,
    s3_url,
    service_type="AWS Service",
):
    """Send email notification via SNS"""
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

    if not sns_topic_arn:
        print("SNS_TOPIC_ARN not configured")
        return False

    try:
        sns = boto3.client("sns")
        summary = summarize_agent_analysis(agent_analysis)

        email_message = f"""ALERT: {service_type} issue detected - {service_name}
Timestamp: {timestamp}

AI Agent Analysis Summary:
{summary}

Full Analysis: {s3_url}

Alert ID: {alert_id}
"""

        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=f"{service_type} Alert: {service_name}",
            Message=email_message,
        )
        print("Email notification sent via SNS")
        return True
    except Exception as e:
        print(f"Failed to send SNS notification: {e}")
        return False


def send_teams_notification(
    service_name,
    timestamp,
    agent_analysis,
    alert_id,
    s3_url,
    service_type="AWS Service",
    status="ISSUE DETECTED",
):
    """Send notification to Microsoft Teams with Adaptive Card"""
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

    if not webhook_url:
        print("TEAMS_WEBHOOK_URL environment variable not set")
        return False

    summary_text = summarize_agent_analysis(agent_analysis)

    # Build Adaptive Card
    card_body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": f"⚠️ {service_type} Alert: {service_name}",
            "wrap": True,
            "color": "Attention",
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Service/Resource:", "value": service_name},
                {"title": "Type:", "value": service_type},
                {"title": "Status:", "value": status},
                {"title": "Timestamp:", "value": timestamp},
                {"title": "Alert ID:", "value": alert_id},
            ],
        },
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

    # Add action buttons
    actions = []

    # Get API Gateway URL for approval
    approval_api_url = os.environ.get("APPROVAL_API_URL")

    if approval_api_url:
        # Approval button
        actions.append(
            {
                "type": "Action.OpenUrl",
                "title": "✅ Approve & Execute",
                "url": f"{approval_api_url}?alert_id={alert_id}&action=approve",
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
                    "actions": actions,
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
    except Exception as e:
        print(f"Failed to send Teams notification: {e}")
        return False


def send_slack_notification(
    service_name,
    timestamp,
    agent_analysis,
    alert_id,
    s3_url,
    service_type="AWS Service",
    status="ISSUE DETECTED",
):
    """Send notification to Slack via webhook"""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("SLACK_WEBHOOK_URL environment variable not set")
        return False

    summary_text = summarize_agent_analysis(agent_analysis)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"ALERT: {service_type} - {service_name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Service/Resource:*\n{service_name}"},
                {"type": "mrkdwn", "text": f"*Type:*\n{service_type}"},
                {"type": "mrkdwn", "text": f"*Status:*\n{status}"},
                {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
                {"type": "mrkdwn", "text": f"*Alert ID:*\n`{alert_id}`"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*🤖 AI Agent Analysis Summary:*\n{summary_text[:2800]}",
            },
        },
    ]

    if s3_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"<{s3_url}|📄 View Full Analysis>",
                },
            }
        )

    message = {
        "blocks": blocks,
        "attachments": [
            {
                "color": "#FF0000",
                "fallback": f"{service_type} {service_name} - {status}",
            }
        ],
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
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")
        return False


def lambda_handler(event, context):
    """
    Main Lambda handler for general AWS service analysis
    Receives service issue details from upstream monitoring Lambda functions

    Expected Event Structure:
    {
        "service_name": "my-cloudfront-distribution" or "my-domain.com",
        "service_type": "CloudFront" or "Route53" or "EC2" etc.,
        "error_details": "Description of the error",
        "issue_type": "distribution_error" or "dns_failure" etc.,
        "severity": "critical" or "high" or "medium" or "low",
        "status": "DOWN" or "DEGRADED" or "ERROR",
        "context": {
            "aws_services": ["List of related AWS services"],
            "additional_info": "Any additional context"
        },
        "metadata": {"key": "value"}  // Optional additional metadata
    }
    """
    timestamp = datetime.now().isoformat()

    # Extract service details from event
    service_name = event.get("service_name")
    service_type = event.get("service_type", "AWS Service")
    error_details = event.get("error_details", "Unknown error")
    issue_type = event.get("issue_type", "service_issue")
    severity = event.get("severity", "high")
    status = event.get("status", "ISSUE DETECTED")
    service_context = event.get("context", None)
    additional_metadata = event.get("metadata", None)

    # Validate required fields
    if not service_name:
        print("ERROR: service_name is required in event")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "service_name is required"}),
        }

    print(f"Starting analysis for {service_type}: {service_name}")
    print(f"Issue: {error_details}")
    print(f"Severity: {severity}")

    try:
        # Generate unique alert ID
        alert_id = str(uuid.uuid4())

        # Invoke AI agent for analysis with context
        print("Invoking agent for comprehensive analysis...")
        agent_analysis, agent_session_id = invoke_agent_for_analysis(
            service_name, timestamp, error_details, service_context
        )

        if not agent_analysis:
            print("Agent analysis failed, sending basic alert")
            agent_analysis = f"Agent analysis unavailable. Error: {error_details}"
            agent_session_id = None

        # Upload full analysis to S3
        s3_url, s3_key = upload_analysis_to_s3(
            alert_id, service_name, timestamp, agent_analysis, service_type
        )

        # Store alert metadata in DynamoDB
        store_alert_in_dynamodb(
            alert_id,
            service_name,
            timestamp,
            error_details,
            agent_analysis,
            agent_session_id,
            s3_url,
            s3_key,
            service_type,
            issue_type,
            severity,
            additional_metadata,
        )

        # Send notifications to all channels
        print("Sending notifications...")

        # Email via SNS
        send_sns_notification(
            service_name, timestamp, alert_id, agent_analysis, s3_url, service_type
        )

        # Teams with Adaptive Card
        send_teams_notification(
            service_name,
            timestamp,
            agent_analysis,
            alert_id,
            s3_url,
            service_type,
            status,
        )

        # Slack (if configured)
        send_slack_notification(
            service_name,
            timestamp,
            agent_analysis,
            alert_id,
            s3_url,
            service_type,
            status,
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": f"Analysis completed for {service_type}: {service_name}",
                    "alert_id": alert_id,
                    "timestamp": timestamp,
                    "s3_url": s3_url,
                    "agent_session_id": agent_session_id,
                    "severity": severity,
                }
            ),
        }

    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
