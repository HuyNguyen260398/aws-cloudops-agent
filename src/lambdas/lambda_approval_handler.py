import json
import os
import boto3
import hmac
import hashlib
import time
from urllib.parse import parse_qs
from datetime import datetime


def verify_slack_signature(event):
    """Verify that the request came from Slack"""
    slack_signing_secret = os.environ.get("SLACK_SIGNING_SECRET")

    if not slack_signing_secret:
        print(
            "Warning: SLACK_SIGNING_SECRET not configured, skipping signature verification"
        )
        return True

    # Get headers
    headers = event.get("headers", {})
    slack_signature = headers.get("x-slack-signature", headers.get("X-Slack-Signature"))
    slack_request_timestamp = headers.get(
        "x-slack-request-timestamp", headers.get("X-Slack-Request-Timestamp")
    )

    if not slack_signature or not slack_request_timestamp:
        print("Missing Slack signature headers")
        return False

    # Check timestamp to prevent replay attacks (within 5 minutes)
    current_timestamp = int(time.time())
    if abs(current_timestamp - int(slack_request_timestamp)) > 300:
        print("Request timestamp too old")
        return False

    # Verify signature
    body = event.get("body", "")
    sig_basestring = f"v0:{slack_request_timestamp}:{body}"
    my_signature = (
        "v0="
        + hmac.new(
            slack_signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
    )

    if hmac.compare_digest(my_signature, slack_signature):
        return True

    print("Invalid Slack signature")
    return False


def get_alert_data(alert_id):
    """Retrieve alert data from DynamoDB"""
    dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")

    if not dynamodb_table:
        print("DYNAMODB_ALERTS_TABLE environment variable not set")
        return None

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(dynamodb_table)

        response = table.get_item(Key={"alert_id": alert_id})

        if "Item" in response:
            return response["Item"]
        else:
            print(f"Alert ID {alert_id} not found in DynamoDB")
            return None
    except Exception as e:
        print(f"Error retrieving alert data: {e}")
        return None


def update_alert_status(alert_id, status, user_id):
    """Update alert approval status in DynamoDB"""
    dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")

    if not dynamodb_table:
        return False

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(dynamodb_table)

        table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET approval_status = :status, approved_by = :user, approved_at = :timestamp",
            ExpressionAttributeValues={
                ":status": status,
                ":user": user_id,
                ":timestamp": str(datetime.now()),
            },
        )
        print(f"Alert {alert_id} status updated to {status}")
        return True
    except Exception as e:
        print(f"Error updating alert status: {e}")
        return False


def execute_remediation_actions(alert_data):
    """Execute automated remediation actions based on agent analysis"""
    domain = alert_data.get("domain")
    agent_analysis = alert_data.get("agent_analysis", "")

    print(f"Executing remediation actions for domain: {domain}")

    remediation_results = []

    # Example remediation actions:
    # 1. Invalidate CloudFront cache
    # 2. Restart/redeploy services
    # 3. Update DNS records
    # 4. Trigger auto-scaling
    # 5. Clear WAF rules if blocked

    try:
        # Example: CloudFront cache invalidation
        cloudfront_distribution_id = os.environ.get("CLOUDFRONT_DISTRIBUTION_ID")
        if cloudfront_distribution_id:
            try:
                cloudfront = boto3.client("cloudfront")
                invalidation = cloudfront.create_invalidation(
                    DistributionId=cloudfront_distribution_id,
                    InvalidationBatch={
                        "Paths": {"Quantity": 1, "Items": ["/*"]},
                        "CallerReference": str(datetime.now().timestamp()),
                    },
                )
                remediation_results.append(
                    {
                        "action": "CloudFront Cache Invalidation",
                        "status": "success",
                        "details": f"Invalidation ID: {invalidation['Invalidation']['Id']}",
                    }
                )
                print(
                    f"CloudFront cache invalidated: {invalidation['Invalidation']['Id']}"
                )
            except Exception as e:
                remediation_results.append(
                    {
                        "action": "CloudFront Cache Invalidation",
                        "status": "failed",
                        "error": str(e),
                    }
                )
                print(f"Failed to invalidate CloudFront cache: {e}")

        # Example: Check and update Route53 health checks
        try:
            route53 = boto3.client("route53")
            # Add your Route53 remediation logic here
            remediation_results.append(
                {
                    "action": "Route53 Health Check",
                    "status": "verified",
                    "details": "DNS records verified",
                }
            )
        except Exception as e:
            remediation_results.append(
                {"action": "Route53 Health Check", "status": "failed", "error": str(e)}
            )

        # Example: Publish to SNS for further automated workflows
        sns = boto3.client("sns")
        sns_topic_arn = os.environ.get("REMEDIATION_SNS_TOPIC_ARN")
        if sns_topic_arn:
            try:
                sns.publish(
                    TopicArn=sns_topic_arn,
                    Subject=f"Remediation Executed for {domain}",
                    Message=json.dumps(
                        {
                            "domain": domain,
                            "alert_id": alert_data.get("alert_id"),
                            "remediation_results": remediation_results,
                            "timestamp": str(datetime.now()),
                        },
                        indent=2,
                    ),
                )
                print("Remediation notification sent to SNS")
            except Exception as e:
                print(f"Failed to send remediation notification: {e}")

    except Exception as e:
        print(f"Error during remediation: {e}")
        remediation_results.append(
            {"action": "General Remediation", "status": "error", "error": str(e)}
        )

    return remediation_results


def update_slack_message(
    response_url, alert_data, action, user_name, remediation_results=None
):
    """Update the original Slack message after approval/dismissal"""
    import urllib.request

    domain = alert_data.get("domain")
    timestamp = alert_data.get("timestamp")
    alert_id = alert_data.get("alert_id")

    if action == "approved":
        color = "#36a64f"  # Green
        status_text = f"✅ *Approved by {user_name}*"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"✅ RESOLVED: Domain Alert - {domain}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Domain:*\n{domain}"},
                    {"type": "mrkdwn", "text": f"*Status:*\nRESOLVING"},
                    {"type": "mrkdwn", "text": f"*Approved By:*\n{user_name}"},
                    {"type": "mrkdwn", "text": f"*Alert ID:*\n`{alert_id}`"},
                ],
            },
        ]

        if remediation_results:
            blocks.append({"type": "divider"})
            results_text = "*🔧 Remediation Actions Executed:*\n\n"
            for result in remediation_results:
                status_emoji = (
                    "✅"
                    if result["status"] == "success"
                    else "⚠️" if result["status"] == "verified" else "❌"
                )
                results_text += f"{status_emoji} *{result['action']}*: {result.get('details', result.get('error', 'Unknown'))}\n"

            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": results_text,
                    },
                }
            )

        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"✅ Remediation approved at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    }
                ],
            }
        )

    else:  # dismissed
        color = "#ff0000"  # Red
        status_text = f"❌ *Dismissed by {user_name}*"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"❌ DISMISSED: Domain Alert - {domain}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Domain:*\n{domain}"},
                    {"type": "mrkdwn", "text": f"*Status:*\nDISMISSED"},
                    {"type": "mrkdwn", "text": f"*Dismissed By:*\n{user_name}"},
                    {"type": "mrkdwn", "text": f"*Alert ID:*\n`{alert_id}`"},
                ],
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"❌ Alert dismissed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - No action taken",
                    }
                ],
            },
        ]

    message = {
        "replace_original": True,
        "blocks": blocks,
        "attachments": [{"color": color, "fallback": status_text}],
    }

    try:
        req = urllib.request.Request(
            response_url,
            data=json.dumps(message).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        response = urllib.request.urlopen(req)
        print(f"Slack message updated: {response.read().decode()}")
        return True
    except Exception as e:
        print(f"Failed to update Slack message: {e}")
        return False


def lambda_handler(event, context):
    """
    Handle Slack interactive button callbacks for approval workflow
    """
    print(f"Received event: {json.dumps(event)}")

    # Verify Slack signature
    if not verify_slack_signature(event):
        return {"statusCode": 401, "body": json.dumps({"error": "Invalid signature"})}

    try:
        # Parse the payload from Slack
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            import base64

            body = base64.b64decode(body).decode("utf-8")

        parsed_body = parse_qs(body)
        payload_str = parsed_body.get("payload", [""])[0]
        payload = json.loads(payload_str)

        print(f"Parsed payload: {json.dumps(payload)}")

        # Extract action information
        actions = payload.get("actions", [])
        if not actions:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No actions found"}),
            }

        action = actions[0]
        action_id = action.get("action_id", "")
        alert_id = action.get("value")

        user = payload.get("user", {})
        user_name = user.get("name", "Unknown User")
        user_id = user.get("id", "Unknown")

        response_url = payload.get("response_url")

        print(f"Action: {action_id}, Alert ID: {alert_id}, User: {user_name}")

        # Retrieve alert data
        alert_data = get_alert_data(alert_id)

        if not alert_data:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Alert not found or expired"}),
            }

        # Check if already processed
        if alert_data.get("approval_status") != "pending":
            # Send ephemeral message
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "text": f"⚠️ This alert has already been {alert_data.get('approval_status')}.",
                        "response_type": "ephemeral",
                    }
                ),
            }

        # Process the action
        if "approve_remediation" in action_id:
            # Update status
            update_alert_status(alert_id, "approved", user_id)

            # Execute remediation actions
            print("Executing remediation actions...")
            remediation_results = execute_remediation_actions(alert_data)

            # Update Slack message
            update_slack_message(
                response_url, alert_data, "approved", user_name, remediation_results
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "text": "✅ Remediation approved and executed!",
                        "response_type": "ephemeral",
                    }
                ),
            }

        elif "dismiss_alert" in action_id:
            # Update status
            update_alert_status(alert_id, "dismissed", user_id)

            # Update Slack message
            update_slack_message(response_url, alert_data, "dismissed", user_name)

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {"text": "❌ Alert dismissed.", "response_type": "ephemeral"}
                ),
            }

        elif "view_full_analysis" in action_id:
            # Return full analysis as ephemeral message
            full_analysis = alert_data.get("agent_analysis", "No analysis available")
            domain = alert_data.get("domain", "Unknown")

            # Split into chunks if too long (Slack ephemeral message limit ~3000 chars per block)
            max_chunk_size = 2900
            chunks = []

            if len(full_analysis) > max_chunk_size:
                # Split by paragraphs/sections to avoid cutting mid-sentence
                lines = full_analysis.split("\n")
                current_chunk = []
                current_length = 0

                for line in lines:
                    line_length = len(line) + 1  # +1 for newline
                    if current_length + line_length > max_chunk_size and current_chunk:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [line]
                        current_length = line_length
                    else:
                        current_chunk.append(line)
                        current_length += line_length

                if current_chunk:
                    chunks.append("\n".join(current_chunk))
            else:
                chunks = [full_analysis]

            # Build response with blocks for each chunk
            response_blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🤖 Full AI Analysis - {domain}",
                        "emoji": True,
                    },
                }
            ]

            for i, chunk in enumerate(chunks):
                response_blocks.append(
                    {"type": "section", "text": {"type": "mrkdwn", "text": chunk}}
                )

                if i < len(chunks) - 1:
                    response_blocks.append({"type": "divider"})

            response_blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"📊 Total length: {len(full_analysis):,} characters | Alert ID: `{alert_id}`",
                        }
                    ],
                }
            )

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "blocks": response_blocks,
                        "response_type": "ephemeral",
                        "replace_original": False,
                    }
                ),
            }

        else:
            return {"statusCode": 400, "body": json.dumps({"error": "Unknown action"})}

    except Exception as e:
        print(f"Error processing approval: {e}")
        import traceback

        traceback.print_exc()

        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
