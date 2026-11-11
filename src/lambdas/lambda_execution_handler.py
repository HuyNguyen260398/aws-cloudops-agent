"""
Lambda Function: Execution Handler
Execute agent recommendations after approval with context retention
Triggered by SNS from approval handler
"""

import boto3
import json
import os
from datetime import datetime
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert DynamoDB Decimal types to JSON"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
sns = boto3.client("sns")


def lambda_handler(event, context):
    """
    Execute agent recommendations with context retention
    Triggered by SNS message from approval handler
    """
    print(
        f"Execution handler invoked with event: {json.dumps(event, cls=DecimalEncoder)}"
    )

    # Parse SNS event
    try:
        if "Records" in event and len(event["Records"]) > 0:
            # SNS trigger
            sns_message = event["Records"][0]["Sns"]["Message"]
            execution_request = json.loads(sns_message)
        else:
            # Direct invocation
            execution_request = event

        alert_id = execution_request.get("alert_id")
        if not alert_id:
            print("ERROR: alert_id not found in execution request")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "alert_id is required"}),
            }

        print(f"Processing execution for alert {alert_id}")

        # Retrieve alert data from DynamoDB
        alert_data = get_alert_from_dynamodb(alert_id)

        if not alert_data:
            print(f"ERROR: Alert {alert_id} not found in DynamoDB")
            return {"statusCode": 404, "body": json.dumps({"error": "Alert not found"})}

        # Validate alert is approved
        if alert_data.get("approval_status") != "approved":
            print(
                f"ERROR: Alert {alert_id} is not approved: {alert_data.get('approval_status')}"
            )
            return {
                "statusCode": 400,
                "body": json.dumps(
                    {
                        "error": f"Alert is {alert_data.get('approval_status')}, not approved"
                    }
                ),
            }

        # Extract context from alert
        domain = alert_data.get("domain")
        agent_session_id = alert_data.get("agent_session_id")
        s3_analysis_key = alert_data.get("s3_analysis_key")

        print(f"Domain: {domain}, Session ID: {agent_session_id}")

        # Retrieve full analysis from S3
        full_analysis = None
        if s3_analysis_key:
            full_analysis = get_analysis_from_s3(s3_analysis_key)

        if not full_analysis:
            print("WARNING: Could not retrieve full analysis from S3")
            full_analysis = alert_data.get("agent_analysis", "")

        # Execute agent recommendations with context retention
        execution_result = execute_with_agent(
            domain=domain,
            full_analysis=full_analysis,
            session_id=agent_session_id,
            alert_id=alert_id,
        )

        # Update DynamoDB with execution status
        update_execution_status(
            alert_id=alert_id,
            status="completed" if execution_result["success"] else "failed",
            execution_log=execution_result["execution_log"],
            execution_details=execution_result["details"],
        )

        # Upload execution results to S3
        execution_s3_key = upload_execution_results(
            alert_id=alert_id, domain=domain, execution_result=execution_result
        )

        # Send notifications
        send_execution_notifications(
            alert_data=alert_data,
            execution_result=execution_result,
            execution_s3_key=execution_s3_key,
        )

        print(f"Execution completed for alert {alert_id}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Execution completed",
                    "alert_id": alert_id,
                    "success": execution_result["success"],
                    "execution_log_url": f"s3://{os.environ.get('S3_ANALYSIS_BUCKET')}/{execution_s3_key}",
                },
                cls=DecimalEncoder,
            ),
        }

    except Exception as e:
        print(f"ERROR: Execution failed: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "body": json.dumps({"error": f"Execution failed: {str(e)}"}),
        }


def get_alert_from_dynamodb(alert_id):
    """Retrieve alert data from DynamoDB"""
    try:
        dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")
        if not dynamodb_table:
            print("ERROR: DYNAMODB_ALERTS_TABLE environment variable not set")
            return None

        table = dynamodb.Table(dynamodb_table)
        response = table.get_item(Key={"alert_id": alert_id})

        if "Item" in response:
            return response["Item"]
        else:
            return None
    except Exception as e:
        print(f"Error retrieving alert from DynamoDB: {e}")
        return None


def get_analysis_from_s3(s3_key):
    """Retrieve full analysis from S3"""
    try:
        s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET")
        if not s3_bucket:
            print("ERROR: S3_ANALYSIS_BUCKET environment variable not set")
            return None

        response = s3.get_object(Bucket=s3_bucket, Key=s3_key)
        analysis_content = response["Body"].read().decode("utf-8")

        print(f"Retrieved analysis from S3: {len(analysis_content)} characters")
        return analysis_content
    except Exception as e:
        print(f"Error retrieving analysis from S3: {e}")
        return None


def execute_with_agent(domain, full_analysis, session_id, alert_id):
    """
    Execute agent recommendations with context retention
    Uses the same session_id to maintain conversation context
    """
    print(f"Executing recommendations for domain: {domain}")
    print(f"Using session_id: {session_id}")

    try:
        # Construct execution prompt with context from analysis
        execution_prompt = construct_execution_prompt(domain, full_analysis)

        # Invoke agent with context retention
        execution_response = invoke_agent_for_execution(
            prompt=execution_prompt, session_id=session_id
        )

        print(f"Agent execution response: {len(execution_response)} characters")

        # Parse execution results
        execution_log = parse_execution_log(execution_response)

        return {
            "success": True,
            "execution_log": execution_response,
            "details": execution_log,
        }

    except Exception as e:
        print(f"Error during agent execution: {e}")
        import traceback

        traceback.print_exc()

        return {
            "success": False,
            "execution_log": f"Execution failed: {str(e)}",
            "details": {"error": str(e), "traceback": traceback.format_exc()},
        }


def construct_execution_prompt(domain, full_analysis):
    """
    Construct execution prompt with context from analysis
    References the previous analysis to maintain context
    """
    prompt = f"""Based on our previous analysis of {domain}, I need you to execute the recommended remediation actions.

PREVIOUS ANALYSIS SUMMARY:
{full_analysis[:2000]}  # Include first 2000 chars of analysis for context

EXECUTION INSTRUCTIONS:
Now that the analysis has been approved, please execute the following actions:

1. **Immediate Actions**: Execute any critical remediation steps identified in the analysis
2. **Configuration Changes**: Apply recommended configuration changes
3. **Verification**: Verify that each action completes successfully
4. **Rollback Plan**: Be prepared to rollback if any action fails
5. **Documentation**: Log all actions taken with timestamps

For each action, provide:
- Action taken
- Timestamp
- Status (Success/Failed/Skipped)
- Any errors or warnings
- Verification results

IMPORTANT: 
- Only execute actions that were explicitly recommended in the analysis
- Use AWS APIs and CLI commands where appropriate
- Verify domain {domain} is accessible after each critical action
- Log all changes for audit purposes

Please proceed with execution and provide detailed results.
"""

    return prompt


def invoke_agent_for_execution(prompt, session_id):
    """
    Invoke Bedrock Agent for execution with session retention
    Reuses the same session_id from analysis phase
    """
    try:
        from components.auth import get_cognito_jwt

        # Get authentication token
        cognito_username = os.environ.get("COGNITO_USERNAME")
        cognito_password = os.environ.get("COGNITO_PASSWORD")
        cognito_client_id = os.environ.get("COGNITO_CLIENT_ID")

        if not all([cognito_username, cognito_password, cognito_client_id]):
            raise ValueError("Cognito credentials not configured")

        id_token = get_cognito_jwt(
            username=cognito_username,
            password=cognito_password,
            client_id=cognito_client_id,
        )

        # Invoke agent runtime with session retention
        agent_runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
        if not agent_runtime_arn:
            raise ValueError("AGENT_RUNTIME_ARN not configured")

        # Parse ARN to get components
        arn_parts = agent_runtime_arn.split(":")
        region = arn_parts[3]
        agent_id = arn_parts[5].split("/")[1]
        agent_alias_id = arn_parts[5].split("/")[3]

        # Create Bedrock Agent Runtime client
        bedrock_agent_runtime = boto3.client(
            service_name="bedrock-agent-runtime", region_name=region
        )

        # Invoke agent with session retention
        print(f"Invoking agent for execution with session: {session_id}")

        response = bedrock_agent_runtime.invoke_agent(
            agentId=agent_id,
            agentAliasId=agent_alias_id,
            sessionId=session_id,  # CRITICAL: Reuse session for context
            inputText=prompt,
            sessionState={
                "sessionAttributes": {
                    "phase": "execution",
                    "timestamp": datetime.now().isoformat(),
                }
            },
        )

        # Process streaming response
        execution_response = ""
        for event in response.get("completion", []):
            if "chunk" in event:
                chunk_data = event["chunk"]
                if "bytes" in chunk_data:
                    execution_response += chunk_data["bytes"].decode("utf-8")

        return execution_response

    except Exception as e:
        print(f"Error invoking agent for execution: {e}")
        raise


def parse_execution_log(execution_response):
    """
    Parse execution response to extract structured log
    Returns dictionary of executed actions with status
    """
    execution_log = {
        "actions": [],
        "summary": {"total_actions": 0, "successful": 0, "failed": 0, "skipped": 0},
    }

    try:
        # Simple parsing - look for action markers
        lines = execution_response.split("\n")

        current_action = None
        for line in lines:
            line_lower = line.lower()

            # Detect action start
            if "action:" in line_lower or "executing:" in line_lower:
                if current_action:
                    execution_log["actions"].append(current_action)

                current_action = {
                    "description": line.strip(),
                    "status": "unknown",
                    "timestamp": datetime.now().isoformat(),
                }

            # Detect status
            elif current_action:
                if "success" in line_lower or "✓" in line or "✅" in line:
                    current_action["status"] = "success"
                    execution_log["summary"]["successful"] += 1
                elif (
                    "fail" in line_lower
                    or "error" in line_lower
                    or "✗" in line
                    or "❌" in line
                ):
                    current_action["status"] = "failed"
                    execution_log["summary"]["failed"] += 1
                elif "skip" in line_lower:
                    current_action["status"] = "skipped"
                    execution_log["summary"]["skipped"] += 1

        # Add last action
        if current_action:
            execution_log["actions"].append(current_action)

        execution_log["summary"]["total_actions"] = len(execution_log["actions"])

    except Exception as e:
        print(f"Error parsing execution log: {e}")

    return execution_log


def update_execution_status(alert_id, status, execution_log, execution_details):
    """Update DynamoDB with execution status"""
    try:
        dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")
        if not dynamodb_table:
            print("ERROR: DYNAMODB_ALERTS_TABLE not set")
            return False

        table = dynamodb.Table(dynamodb_table)

        table.update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="""
                SET execution_status = :status,
                    executed_at = :time,
                    execution_log = :log,
                    execution_details = :details
            """,
            ExpressionAttributeValues={
                ":status": status,
                ":time": datetime.now().isoformat(),
                ":log": execution_log,
                ":details": json.dumps(execution_details, cls=DecimalEncoder),
            },
        )

        print(f"Execution status updated in DynamoDB: {status}")
        return True

    except Exception as e:
        print(f"Error updating execution status: {e}")
        return False


def upload_execution_results(alert_id, domain, execution_result):
    """Upload execution results to S3 as markdown"""
    try:
        s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET")
        if not s3_bucket:
            print("ERROR: S3_ANALYSIS_BUCKET not set")
            return None

        # Create markdown document
        markdown_content = f"""# Execution Results: {domain}

**Alert ID:** `{alert_id}`
**Execution Time:** {datetime.now().isoformat()}
**Status:** {'✅ SUCCESS' if execution_result['success'] else '❌ FAILED'}

---

## Execution Log

```
{execution_result['execution_log']}
```

---

## Execution Summary

"""

        # Add structured summary
        if "details" in execution_result and "summary" in execution_result["details"]:
            summary = execution_result["details"]["summary"]
            markdown_content += f"""
- **Total Actions:** {summary.get('total_actions', 0)}
- **Successful:** {summary.get('successful', 0)} ✅
- **Failed:** {summary.get('failed', 0)} ❌
- **Skipped:** {summary.get('skipped', 0)} ⏭️

### Actions Performed

"""

            for action in execution_result["details"].get("actions", []):
                status_icon = {
                    "success": "✅",
                    "failed": "❌",
                    "skipped": "⏭️",
                    "unknown": "❓",
                }.get(action.get("status"), "❓")

                markdown_content += f"{status_icon} **{action.get('description')}**\n"
                markdown_content += f"   - Status: {action.get('status')}\n"
                markdown_content += f"   - Time: {action.get('timestamp')}\n\n"

        markdown_content += "\n---\n\n*Execution completed by AWS CloudOps Agent*\n"

        # Generate S3 key
        now = datetime.now()
        s3_key = f"executions/{now.strftime('%Y-%m-%d')}/{domain}/{now.strftime('%H-%M-%S')}-{alert_id}.md"

        # Upload to S3
        s3.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=markdown_content.encode("utf-8"),
            ContentType="text/markdown",
        )

        print(f"Execution results uploaded to s3://{s3_bucket}/{s3_key}")

        return s3_key

    except Exception as e:
        print(f"Error uploading execution results: {e}")
        return None


def send_execution_notifications(alert_data, execution_result, execution_s3_key):
    """Send execution completion notifications to all channels"""
    print("Sending execution notifications")

    domain = alert_data.get("domain")
    alert_id = alert_data.get("alert_id")

    # Generate S3 URL
    s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET")
    execution_url = None
    if execution_s3_key and s3_bucket:
        execution_url = f"https://{s3_bucket}.s3.amazonaws.com/{execution_s3_key}"

    # Send to Teams
    send_teams_execution_notification(
        domain=domain,
        alert_id=alert_id,
        execution_result=execution_result,
        execution_url=execution_url,
    )

    # Send to Slack
    send_slack_execution_notification(
        domain=domain,
        alert_id=alert_id,
        execution_result=execution_result,
        execution_url=execution_url,
    )

    # Send email via SNS
    send_email_execution_notification(
        domain=domain,
        alert_id=alert_id,
        execution_result=execution_result,
        execution_url=execution_url,
        alert_data=alert_data,
    )


def send_teams_execution_notification(
    domain, alert_id, execution_result, execution_url
):
    """Send execution notification to Teams"""
    webhook_url = os.environ.get("TEAMS_WEBHOOK_URL")

    if not webhook_url:
        print("TEAMS_WEBHOOK_URL not configured")
        return False

    from urllib.request import Request, urlopen

    success = execution_result["success"]
    icon = "✅" if success else "❌"
    color = "Good" if success else "Attention"
    title = f"{icon} Execution {'Completed' if success else 'Failed'}: {domain}"

    card_body = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": title,
            "wrap": True,
            "color": color,
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Alert ID:", "value": alert_id},
                {"title": "Domain:", "value": domain},
                {"title": "Status:", "value": "SUCCESS" if success else "FAILED"},
                {
                    "title": "Completed:",
                    "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            ],
        },
    ]

    # Add summary if available
    if "details" in execution_result and "summary" in execution_result["details"]:
        summary = execution_result["details"]["summary"]
        card_body.extend(
            [
                {"type": "TextBlock", "text": "---", "separator": True},
                {
                    "type": "TextBlock",
                    "text": f"**Execution Summary:**\n\n- Total Actions: {summary.get('total_actions', 0)}\n- Successful: {summary.get('successful', 0)} ✅\n- Failed: {summary.get('failed', 0)} ❌\n- Skipped: {summary.get('skipped', 0)} ⏭️",
                    "wrap": True,
                },
            ]
        )

    # Add view results button
    if execution_url:
        card_body.append(
            {
                "type": "ActionSet",
                "actions": [
                    {
                        "type": "Action.OpenUrl",
                        "title": "📄 View Execution Log",
                        "url": execution_url,
                    }
                ],
            }
        )

    adaptive_card = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": card_body,
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
        print(f"Teams execution notification sent")
        return True
    except Exception as e:
        print(f"Failed to send Teams notification: {e}")
        return False


def send_slack_execution_notification(
    domain, alert_id, execution_result, execution_url
):
    """Send execution notification to Slack"""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        print("SLACK_WEBHOOK_URL not configured")
        return False

    from urllib.request import Request, urlopen

    success = execution_result["success"]
    icon = ":white_check_mark:" if success else ":x:"
    color = "#00FF00" if success else "#FF0000"

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{icon} Execution {'Completed' if success else 'Failed'}: {domain}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Alert ID:*\n`{alert_id}`"},
                {"type": "mrkdwn", "text": f"*Domain:*\n{domain}"},
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\n{'SUCCESS' if success else 'FAILED'}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Completed:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                },
            ],
        },
    ]

    # Add summary
    if "details" in execution_result and "summary" in execution_result["details"]:
        summary = execution_result["details"]["summary"]
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Execution Summary:*\n• Total: {summary.get('total_actions', 0)}\n• Success: {summary.get('successful', 0)} ✅\n• Failed: {summary.get('failed', 0)} ❌\n• Skipped: {summary.get('skipped', 0)} ⏭️",
                },
            }
        )

    # Add view button
    if execution_url:
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📄 View Execution Log"},
                        "url": execution_url,
                    }
                ],
            }
        )

    message = {
        "blocks": blocks,
        "attachments": [
            {
                "color": color,
                "fallback": f"Execution {alert_id} {'completed' if success else 'failed'}",
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
        print(f"Slack execution notification sent")
        return True
    except Exception as e:
        print(f"Failed to send Slack notification: {e}")
        return False


def send_email_execution_notification(
    domain, alert_id, execution_result, execution_url, alert_data
):
    """Send execution notification via SNS email"""
    sns_topic_arn = os.environ.get("SNS_TOPIC_ARN")

    if not sns_topic_arn:
        print("SNS_TOPIC_ARN not configured")
        return False

    try:
        success = execution_result["success"]
        status_icon = "✅" if success else "❌"

        email_message = f"""{status_icon} Execution {'COMPLETED' if success else 'FAILED'}

Domain: {domain}
Alert ID: {alert_id}
Status: {'SUCCESS' if success else 'FAILED'}
Completed: {datetime.now().isoformat()}

"""

        # Add summary
        if "details" in execution_result and "summary" in execution_result["details"]:
            summary = execution_result["details"]["summary"]
            email_message += f"""Execution Summary:
- Total Actions: {summary.get('total_actions', 0)}
- Successful: {summary.get('successful', 0)}
- Failed: {summary.get('failed', 0)}
- Skipped: {summary.get('skipped', 0)}

"""

        # Add execution log preview
        execution_log = execution_result.get("execution_log", "")
        if len(execution_log) > 1000:
            email_message += f"Execution Log (preview):\n{execution_log[:1000]}...\n\n"
        else:
            email_message += f"Execution Log:\n{execution_log}\n\n"

        if execution_url:
            email_message += f"Full Execution Log: {execution_url}\n"

        sns.publish(
            TopicArn=sns_topic_arn,
            Subject=f"Execution {'Completed' if success else 'Failed'}: {domain}",
            Message=email_message,
        )
        print("Email execution notification sent")
        return True
    except Exception as e:
        print(f"Failed to send email notification: {e}")
        return False
