"""
Lambda Function: Execution Handler (Simplified)
Execute agent recommendations with context retention
Triggered by API Gateway from Teams Execute button
Uses same patterns as analysis Lambda: urllib, Cognito, Bedrock AgentCore
"""

import boto3
import json
import os
import urllib.parse
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

AWS_REGION = "ap-southeast-1"

s3 = boto3.client("s3")
# dynamodb = boto3.resource("dynamodb")  # Commented out - not using DynamoDB in simple version
# sns = boto3.client("sns")  # Commented out - not using SNS in simple version


def get_cognito_jwt_token(username, password, client_id, user_pool_id):
    """Get JWT access token from AWS Cognito (same as analysis Lambda)"""
    # Extract region from User Pool ID (format: region_poolId)
    cognito_region = user_pool_id.split("_")[0] if user_pool_id else "ap-southeast-1"

    print(f"Using Cognito region: {cognito_region} (from pool: {user_pool_id})")
    cognito_client = boto3.client("cognito-idp", region_name=cognito_region)

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


def lambda_handler(event, context):
    """
    Execute agent recommendations with context retention
    Triggered by API Gateway from Teams Execute button

    Expected query parameters:
    - alert_id: Unique alert identifier
    - session_id: Agent session ID from analysis phase
    - service_name: Name of the service being analyzed
    - s3_key: (Optional) S3 key to full analysis
    - async: (Optional) Set to "true" for async invocation
    """
    print(f"Execution handler invoked with event: {json.dumps(event)}")

    try:
        # Parse API Gateway query parameters
        query_params = event.get("queryStringParameters", {}) or {}

        # Check if this is an async background invocation
        is_async = query_params.get("async") == "true"

        if not query_params:
            print("ERROR: No query parameters provided")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "Query parameters required"}),
            }

        alert_id = query_params.get("alert_id")
        session_id = query_params.get("session_id")
        service_name = query_params.get("service_name", "unknown-service")
        s3_analysis_key = query_params.get("s3_key")

        if not alert_id:
            print("ERROR: alert_id is required")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "alert_id is required"}),
            }

        if not session_id:
            print("ERROR: session_id is required")
            return {
                "statusCode": 400,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "session_id is required"}),
            }

        # If NOT async, invoke self asynchronously and return immediate response
        if not is_async:
            print(f"🚀 Triggering async execution for alert {alert_id}")

            # Invoke this same Lambda function asynchronously
            lambda_client = boto3.client("lambda")

            # Create async payload with same params + async flag
            async_params = query_params.copy()
            async_params["async"] = "true"

            async_event = event.copy()
            async_event["queryStringParameters"] = async_params

            try:
                lambda_client.invoke(
                    FunctionName=context.function_name,
                    InvocationType="Event",  # Async invocation
                    Payload=json.dumps(async_event),
                )
                print(f"✅ Async execution triggered successfully")
            except Exception as e:
                print(f"⚠️ Failed to trigger async execution: {e}")

            # Generate S3 bucket reference
            s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET", "cloudops-analysis")
            s3_client = boto3.client("s3", region_name="ap-southeast-1")

            # Try to find the most recent execution file for this alert
            date_str = datetime.now().strftime("%Y-%m-%d")
            safe_service_name = (
                service_name.replace("/", "-").replace(":", "-").replace(" ", "-")
            )
            s3_prefix = f"executions/{date_str}/{safe_service_name}/"

            future_url = None
            try:
                # List objects with the prefix to find files matching this alert
                response = s3_client.list_objects_v2(
                    Bucket=s3_bucket, Prefix=s3_prefix, MaxKeys=50
                )

                # Find the most recent file matching this alert_id
                matching_files = []
                if "Contents" in response:
                    for obj in response["Contents"]:
                        if alert_id in obj["Key"] and obj["Key"].endswith(".md"):
                            matching_files.append(
                                {"Key": obj["Key"], "LastModified": obj["LastModified"]}
                            )

                if matching_files:
                    # Sort by LastModified descending and get the most recent
                    matching_files.sort(key=lambda x: x["LastModified"], reverse=True)
                    latest_file = matching_files[0]["Key"]

                    # Generate pre-signed URL for the actual file
                    future_url = s3_client.generate_presigned_url(
                        "get_object",
                        Params={"Bucket": s3_bucket, "Key": latest_file},
                        ExpiresIn=7200,  # 2 hours
                    )
                    print(f"✅ Found existing execution report: {latest_file}")
                else:
                    print(f"⏳ No execution report found yet in {s3_prefix}")
            except Exception as e:
                print(f"⚠️ Error checking S3 for execution files: {e}")

            # Fallback: provide S3 console URL to browse the execution folder
            if not future_url:
                # S3 console URL for browsing the folder
                future_url = f"https://s3.console.aws.amazon.com/s3/buckets/{s3_bucket}?prefix={s3_prefix}&region=ap-southeast-1"

            # Return immediate HTML response
            html_response = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Execution Started</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                    .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 800px; margin: 0 auto; }}
                    h1 {{ color: #2196F3; }}
                    .spinner {{ border: 4px solid #f3f3f3; border-top: 4px solid #2196F3; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 20px auto; }}
                    @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
                    .detail {{ margin: 10px 0; padding: 10px; background: #f8f9fa; border-left: 3px solid #2196F3; }}
                    a {{ color: #2196F3; text-decoration: none; font-weight: bold; }}
                    a:hover {{ text-decoration: underline; }}
                    .info {{ background: #e3f2fd; padding: 15px; border-radius: 4px; margin: 20px 0; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>⚡ Execution In Progress</h1>
                    <div class="spinner"></div>

                    <div class="detail"><strong>Alert ID:</strong> {alert_id}</div>
                    <div class="detail"><strong>Service:</strong> {service_name}</div>
                    <div class="detail"><strong>Session ID:</strong> {session_id}</div>
                    <div class="detail"><strong>Status:</strong> Processing in background...</div>

                    <div class="info">
                        <strong>ℹ️ What's happening:</strong><br>
                        • AI Agent is analyzing the issue<br>
                        • Executing recommended remediation actions<br>
                        • This typically takes 30-60 seconds<br>
                        • Refresh this page manually to check for the latest report
                    </div>

                    <p><strong>View Results:</strong></p>
                    <p><a href="{future_url}" target="_blank">📄 View Execution Report</a></p>
                    <p><em>Click the link above to view the execution folder. The report will appear within 60 seconds.</em></p>

                    <p style="color: #666; font-size: 12px; margin-top: 30px;">
                        <em>Started at {datetime.now().isoformat()}</em>
                    </p>
                </div>
            </body>
            </html>
            """

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "text/html"},
                "body": html_response,
            }

        # If async=true, proceed with actual execution
        print(f"🔄 Processing execution for alert {alert_id}")
        print(f"📋 Service: {service_name}, Session ID: {session_id}")

        # Retrieve full analysis from S3 if key provided
        full_analysis = None
        if s3_analysis_key:
            full_analysis = get_analysis_from_s3(s3_analysis_key)
            if not full_analysis:
                print("⚠️ Could not retrieve full analysis from S3")

        # Execute agent recommendations with context retention
        execution_result = execute_with_agent(
            service_name=service_name,
            full_analysis=full_analysis,
            session_id=session_id,
            alert_id=alert_id,
        )

        # Upload execution results to S3
        execution_s3_key = upload_execution_results(
            alert_id=alert_id,
            service_name=service_name,
            execution_result=execution_result,
        )

        # Generate S3 URL
        s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET")
        execution_url = None
        if execution_s3_key and s3_bucket:
            execution_url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": s3_bucket, "Key": execution_s3_key},
                ExpiresIn=604800,
            )

        print(f"✅ Execution completed for alert {alert_id}")

        # Return HTML response for browser display
        status_icon = "✅" if execution_result["success"] else "❌"
        status_text = "SUCCESS" if execution_result["success"] else "FAILED"

        html_response = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Execution {status_text}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 800px; margin: 0 auto; }}
                h1 {{ color: {'#28a745' if execution_result['success'] else '#dc3545'}; }}
                .detail {{ margin: 10px 0; padding: 10px; background: #f8f9fa; border-left: 3px solid #007bff; }}
                .log {{ background: #f8f9fa; padding: 15px; border-radius: 4px; white-space: pre-wrap; font-family: monospace; font-size: 12px; max-height: 400px; overflow-y: auto; }}
                a {{ color: #007bff; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{status_icon} Execution {status_text}</h1>
                <div class="detail"><strong>Alert ID:</strong> {alert_id}</div>
                <div class="detail"><strong>Service:</strong> {service_name}</div>
                <div class="detail"><strong>Session ID:</strong> {session_id}</div>
                <div class="detail"><strong>Status:</strong> {status_text}</div>

                <h2>Execution Log:</h2>
                <div class="log">{execution_result.get('execution_log', 'No log available')}</div>

                {f'<p><a href="{execution_url}" target="_blank">📄 View Full Execution Report in S3</a></p>' if execution_url else ''}

                <p><em>Execution completed at {datetime.now().isoformat()}</em></p>
            </div>
        </body>
        </html>
        """

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "text/html"},
            "body": html_response,
        }

    except Exception as e:
        print(f"❌ ERROR: Execution failed: {e}")
        import traceback

        traceback.print_exc()

        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Execution Failed</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); max-width: 800px; margin: 0 auto; }}
                h1 {{ color: #dc3545; }}
                .error {{ background: #f8d7da; color: #721c24; padding: 15px; border-radius: 4px; border: 1px solid #f5c6cb; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>❌ Execution Failed</h1>
                <div class="error">
                    <strong>Error:</strong> {str(e)}
                </div>
                <p><em>Failed at {datetime.now().isoformat()}</em></p>
            </div>
        </body>
        </html>
        """

        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html"},
            "body": error_html,
        }


# def get_alert_from_dynamodb(alert_id):
#     """Retrieve alert data from DynamoDB"""
#     try:
#         dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")
#         if not dynamodb_table:
#             print("ERROR: DYNAMODB_ALERTS_TABLE environment variable not set")
#             return None

#         table = dynamodb.Table(dynamodb_table)
#         response = table.get_item(Key={"alert_id": alert_id})

#         if "Item" in response:
#             return response["Item"]
#         else:
#             return None
#     except Exception as e:
#         print(f"Error retrieving alert from DynamoDB: {e}")
#         return None


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


def execute_with_agent(service_name, full_analysis, session_id, alert_id):
    """
    Execute agent recommendations with context retention
    Uses the same session_id to maintain conversation context
    """
    print(f"⚡ Executing recommendations for service: {service_name}")
    print(f"🔗 Using session_id: {session_id}")

    try:
        # Construct execution prompt with context from analysis
        execution_prompt = construct_execution_prompt(service_name, full_analysis)

        # Invoke agent with context retention (using same API as analysis)
        execution_response = invoke_agent_for_execution(
            prompt=execution_prompt, session_id=session_id
        )

        print(f"📊 Agent execution response: {len(execution_response)} characters")

        # Parse execution results
        execution_log = parse_execution_log(execution_response)

        return {
            "success": True,
            "execution_log": execution_response,
            "details": execution_log,
        }

    except Exception as e:
        print(f"❌ Error during agent execution: {e}")
        import traceback

        traceback.print_exc()

        return {
            "success": False,
            "execution_log": f"Execution failed: {str(e)}",
            "details": {"error": str(e), "traceback": traceback.format_exc()},
        }


def construct_execution_prompt(service_name, full_analysis):
    """
    Construct execution prompt with context from analysis
    References the previous analysis to maintain context
    """
    # Include analysis context if available
    analysis_context = ""
    if full_analysis:
        analysis_context = f"""
**PREVIOUS ANALYSIS SUMMARY:**
{full_analysis[:2000]}

---
"""

    prompt = f"""EXECUTION REQUEST: Based on our previous analysis of {service_name}, execute the recommended remediation actions.

{analysis_context}

**EXECUTION INSTRUCTIONS:**

You are now in the EXECUTION phase. The analysis has been reviewed and you should proceed with the recommended actions.

**Your tasks:**

1. **Review the Analysis**: Recall the "IMMEDIATE ACTIONS REQUIRED" section from your previous analysis

2. **Execute Actions**: Implement each recommended action step-by-step:
   - Use appropriate AWS CLI/SDK commands
   - Apply configuration changes
   - Update resources as needed

3. **Verify Each Step**: After each action, verify it completed successfully:
   - Check resource status
   - Validate configuration changes
   - Confirm expected outcomes

4. **Document Everything**: For each action, provide:
   - Action description
   - Command/API call used
   - Status (✅ Success / ❌ Failed / ⏭️ Skipped)
   - Output/result
   - Verification method

5. **Handle Failures**: If an action fails:
   - Document the error
   - Skip to the next action or stop if critical
   - Provide rollback recommendations

**IMPORTANT GUIDELINES:**
- Only execute actions that were explicitly recommended in your analysis
- Be cautious with destructive operations
- Verify {service_name} remains accessible after critical changes
- Include timestamps for audit trail
- Provide clear success/failure indicators for each action

**OUTPUT FORMAT:** Use clear sections with status indicators (✅/❌/⏭️) for each action.

Begin execution now and provide detailed results.
"""

    return prompt


def invoke_agent_for_execution(prompt, session_id):
    """
    Invoke Bedrock AgentCore API for execution with session retention
    Uses same pattern as analysis Lambda: urllib + Bedrock AgentCore
    Reuses the same session_id from analysis phase for context continuity
    """
    runtime_arn = os.environ.get("AGENT_RUNTIME_ARN")
    cognito_username = os.environ.get("COGNITO_USERNAME")
    cognito_password = os.environ.get("COGNITO_PASSWORD")
    cognito_client_id = os.environ.get("COGNITO_CLIENT_ID")
    cognito_user_pool_id = os.environ.get(
        "COGNITO_USER_POOL_ID", "ap-southeast-1_jjG5DkVCy"
    )

    if not all([runtime_arn, cognito_username, cognito_password, cognito_client_id]):
        raise ValueError(
            "Agent configuration incomplete - missing environment variables"
        )

    print(f"🚀 Invoking Bedrock AgentCore for execution...")

    try:
        # Get JWT token (same as analysis Lambda)
        jwt_token = get_cognito_jwt_token(
            cognito_username, cognito_password, cognito_client_id, cognito_user_pool_id
        )

        if not jwt_token:
            raise ValueError("Failed to obtain JWT token from Cognito")

        # Prepare agent invocation URL (same pattern as analysis)
        escaped_agent_arn = urllib.parse.quote(runtime_arn, safe="")
        url = f"https://bedrock-agentcore.{AWS_REGION}.amazonaws.com/runtimes/{escaped_agent_arn}/invocations?qualifier=DEFAULT"

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        }

        payload = {
            "prompt": prompt,
            "session_id": session_id,  # CRITICAL: Reuse session for context
            "actor_id": cognito_username,
        }

        print(f"📡 Invoking agent with session: {session_id}")

        # Invoke agent with streaming (same as analysis Lambda)
        req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)

        response = urlopen(req, timeout=120)  # Longer timeout for execution

        if response.status in [200, 202]:
            agent_response = ""
            # Collect streaming response
            for line in response:
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

            # Format the agent response - convert escaped characters
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

            print(f"✅ Agent execution completed ({len(formatted_response)} chars)")
            return formatted_response
        else:
            raise Exception(f"Agent invocation failed with status: {response.status}")

    except TimeoutError:
        print("⏱️ Agent request timed out")
        raise
    except URLError as e:
        if isinstance(e.reason, TimeoutError):
            print("⏱️ Agent request timed out")
        else:
            print(f"❌ Error invoking agent: {e}")
        raise
    except Exception as e:
        print(f"❌ Error invoking agent for execution: {e}")
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


# COMMENTED OUT - Not using DynamoDB in simplified version
# def update_execution_status(alert_id, status, execution_log, execution_details):
#     """Update DynamoDB with execution status"""
#     try:
#         dynamodb_table = os.environ.get("DYNAMODB_ALERTS_TABLE")
#         if not dynamodb_table:
#             print("ERROR: DYNAMODB_ALERTS_TABLE not set")
#             return False
#
#         dynamodb = boto3.resource("dynamodb")
#         table = dynamodb.Table(dynamodb_table)
#
#         table.update_item(
#             Key={"alert_id": alert_id},
#             UpdateExpression="""
#                 SET execution_status = :status,
#                     executed_at = :time,
#                     execution_log = :log,
#                     execution_details = :details
#             """,
#             ExpressionAttributeValues={
#                 ":status": status,
#                 ":time": datetime.now().isoformat(),
#                 ":log": execution_log,
#                 ":details": json.dumps(execution_details),
#             },
#         )
#
#         print(f"Execution status updated in DynamoDB: {status}")
#         return True
#
#     except Exception as e:
#         print(f"Error updating execution status: {e}")
#         return False


def upload_execution_results(alert_id, service_name, execution_result):
    """Upload execution results to S3 as markdown"""
    try:
        s3_bucket = os.environ.get("S3_ANALYSIS_BUCKET")
        if not s3_bucket:
            print("⚠️ S3_ANALYSIS_BUCKET not set - skipping S3 upload")
            return None

        # Sanitize service_name for use in path
        safe_service_name = (
            service_name.replace("/", "-").replace(":", "-").replace(" ", "-")
        )

        # Create markdown document
        markdown_content = f"""# Execution Results: {service_name}

**Alert ID:** `{alert_id}`
**Service:** {service_name}
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

        # Generate S3 key (same pattern as analysis results)
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H-%M-%S")
        s3_key = f"executions/{date_str}/{safe_service_name}/{time_str}-{alert_id}.md"

        # Upload to S3
        s3.put_object(
            Bucket=s3_bucket,
            Key=s3_key,
            Body=markdown_content.encode("utf-8"),
            ContentType="text/markdown",
            Metadata={
                "alert-id": alert_id,
                "service-name": safe_service_name,
                "execution-status": (
                    "success" if execution_result["success"] else "failed"
                ),
                "timestamp": now.isoformat(),
            },
        )

        print(f"📤 Execution results uploaded to s3://{s3_bucket}/{s3_key}")

        return s3_key

    except Exception as e:
        print(f"❌ Error uploading execution results: {e}")
        return None
