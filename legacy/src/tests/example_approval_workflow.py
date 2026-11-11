"""
Example: Slack Approval Workflow Response
This file shows example data structures used in the approval workflow
"""

# Example: Alert Data Stored in DynamoDB
ALERT_DATA_EXAMPLE = {
    "alert_id": "550e8400-e29b-41d4-a716-446655440000",
    "domain": "nghuy.link",
    "status": "down",
    "timestamp": "2025-11-22 10:30:00.123456",
    "error_details": "Simulated unreachable domain for testing purposes",
    "agent_analysis": """
🚨 EXECUTIVE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROOT CAUSE: CloudFront distribution returning 503 Service Unavailable

📋 DETAILED ANALYSIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔍 Service Status Check
✅ Route 53: Operational
✅ CloudFront: Operational (no known issues)
⚠️  S3 Origin: Potential latency detected
✅ ACM: Valid certificate (expires in 87 days)
✅ WAF: No blocking rules active

🔍 Configuration Analysis
✅ DNS Resolution: Correct A/AAAA records pointing to CloudFront
⚠️  Health Checks: 2 of 3 health checks failing
✅ Security Groups: Properly configured
❌ Origin Response: Timeout after 30 seconds

🔍 Recent Changes Detected
• 15 minutes ago: S3 bucket policy updated
• 1 hour ago: CloudFront cache behavior modified
• 3 hours ago: Lambda@Edge function deployed

📊 RECOMMENDED ACTIONS (Priority Order)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 🔧 IMMEDIATE: Invalidate CloudFront cache
   → Clear potentially corrupted cache entries
   → Command: aws cloudfront create-invalidation

2. 🔧 IMMEDIATE: Verify S3 bucket policy
   → Recent policy change may have restricted CloudFront access
   → Check: s3:GetObject permission for CloudFront OAI

3. 🔧 SHORT-TERM: Review Lambda@Edge function
   → Recent deployment may be causing origin timeouts
   → Consider rollback if issues persist

4. 📊 MONITORING: Increase CloudWatch alarm sensitivity
   → Current threshold may miss early warnings
   → Add origin latency metric

⏱️  ESTIMATED TIME TO RESOLUTION: 5-10 minutes
💡 CONFIDENCE LEVEL: High (85%)

This analysis was performed at 2025-11-22 10:31:45 UTC
""",
    "approval_status": "pending",
    "ttl": 1732281000,
}

# Example: Slack Message Payload (Interactive Card)
SLACK_MESSAGE_EXAMPLE = {
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🚨 ALERT: Domain Alert - nghuy.link",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Domain:*\nnghuy.link"},
                {"type": "mrkdwn", "text": "*Status:*\nDOWN"},
                {"type": "mrkdwn", "text": "*Timestamp:*\n2025-11-22 10:30:00.123456"},
                {
                    "type": "mrkdwn",
                    "text": "*Alert ID:*\n`550e8400-e29b-41d4-a716-446655440000`",
                },
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🤖 AI Agent Analysis:*\n\n🚨 EXECUTIVE SUMMARY\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nROOT CAUSE: CloudFront distribution returning 503 Service Unavailable\n\n📋 DETAILED ANALYSIS...",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*Review the agent's analysis and approve to execute remediation actions:*",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve & Execute",
                        "emoji": True,
                    },
                    "style": "primary",
                    "value": "550e8400-e29b-41d4-a716-446655440000",
                    "action_id": "approve_remediation_550e8400-e29b-41d4-a716-446655440000",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Dismiss", "emoji": True},
                    "style": "danger",
                    "value": "550e8400-e29b-41d4-a716-446655440000",
                    "action_id": "dismiss_alert_550e8400-e29b-41d4-a716-446655440000",
                },
            ],
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "🔍 Monitored by AWS Lambda | Powered by AI CloudOps Agent",
                }
            ],
        },
    ],
    "attachments": [{"color": "#FF0000", "fallback": "Domain nghuy.link is down"}],
}

# Example: Slack Interactive Callback Payload
SLACK_CALLBACK_EXAMPLE = {
    "type": "block_actions",
    "team": {"id": "T12345678", "domain": "mycompany"},
    "user": {"id": "U12345678", "username": "john.doe", "name": "john.doe"},
    "api_app_id": "A12345678",
    "token": "verification_token",
    "container": {
        "type": "message",
        "message_ts": "1732281000.123456",
        "channel_id": "C12345678",
        "is_ephemeral": False,
    },
    "trigger_id": "trigger_id_value",
    "channel": {"id": "C12345678", "name": "alerts"},
    "message": {
        "type": "message",
        "subtype": "bot_message",
        "text": "Alert message",
        "ts": "1732281000.123456",
        "bot_id": "B12345678",
    },
    "response_url": "https://hooks.slack.com/actions/T12345678/12345678/abcdefg",
    "actions": [
        {
            "action_id": "approve_remediation_550e8400-e29b-41d4-a716-446655440000",
            "block_id": "block_id_value",
            "text": {
                "type": "plain_text",
                "text": "✅ Approve & Execute",
                "emoji": True,
            },
            "value": "550e8400-e29b-41d4-a716-446655440000",
            "style": "primary",
            "type": "button",
            "action_ts": "1732281060.123456",
        }
    ],
}

# Example: Remediation Results
REMEDIATION_RESULTS_EXAMPLE = [
    {
        "action": "CloudFront Cache Invalidation",
        "status": "success",
        "details": "Invalidation ID: I3EXAMPLE123456",
    },
    {
        "action": "Route53 Health Check",
        "status": "verified",
        "details": "DNS records verified",
    },
    {
        "action": "SNS Notification",
        "status": "success",
        "details": "Remediation report sent to operations team",
    },
]

# Example: Updated Slack Message (After Approval)
SLACK_UPDATED_MESSAGE_EXAMPLE = {
    "replace_original": True,
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "✅ RESOLVED: Domain Alert - nghuy.link",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Domain:*\nnghuy.link"},
                {"type": "mrkdwn", "text": "*Status:*\nRESOLVING"},
                {"type": "mrkdwn", "text": "*Approved By:*\njohn.doe"},
                {
                    "type": "mrkdwn",
                    "text": "*Alert ID:*\n`550e8400-e29b-41d4-a716-446655440000`",
                },
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*🔧 Remediation Actions Executed:*\n\n✅ *CloudFront Cache Invalidation*: Invalidation ID: I3EXAMPLE123456\n⚠️ *Route53 Health Check*: DNS records verified\n✅ *SNS Notification*: Remediation report sent to operations team\n",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "✅ Remediation approved at 2025-11-22 10:35:00",
                }
            ],
        },
    ],
    "attachments": [{"color": "#36a64f", "fallback": "✅ Approved by john.doe"}],
}

# Example: Lambda Response (Success)
LAMBDA_RESPONSE_SUCCESS = {
    "statusCode": 500,
    "body": "ALERT: nghuy.link is unreachable at 2025-11-22 10:30:00.123456",
    "alert_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_analysis": "🚨 EXECUTIVE SUMMARY...",
}

# Example: API Gateway Response (Approval)
API_GATEWAY_RESPONSE_EXAMPLE = {
    "statusCode": 200,
    "body": '{"text": "✅ Remediation approved and executed!", "response_type": "ephemeral"}',
}

# Example: DynamoDB Item (After Approval)
DYNAMODB_APPROVED_ITEM = {
    "alert_id": "550e8400-e29b-41d4-a716-446655440000",
    "domain": "nghuy.link",
    "status": "down",
    "timestamp": "2025-11-22 10:30:00.123456",
    "error_details": "Simulated unreachable domain for testing purposes",
    "agent_analysis": "🚨 EXECUTIVE SUMMARY...",
    "approval_status": "approved",
    "approved_by": "U12345678",
    "approved_at": "2025-11-22 10:35:00",
    "ttl": 1732281000,
}

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("Slack Approval Workflow - Example Data")
    print("=" * 60)
    print()

    print("1. Alert Data (DynamoDB):")
    print("-" * 60)
    print(json.dumps(ALERT_DATA_EXAMPLE, indent=2))
    print()

    print("2. Slack Message (Interactive Card):")
    print("-" * 60)
    print(json.dumps(SLACK_MESSAGE_EXAMPLE, indent=2))
    print()

    print("3. Remediation Results:")
    print("-" * 60)
    print(json.dumps(REMEDIATION_RESULTS_EXAMPLE, indent=2))
    print()

    print("4. Updated Slack Message (After Approval):")
    print("-" * 60)
    print(json.dumps(SLACK_UPDATED_MESSAGE_EXAMPLE, indent=2))
    print()
