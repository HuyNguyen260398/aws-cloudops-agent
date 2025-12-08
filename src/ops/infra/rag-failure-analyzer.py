#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lambda Helper: RAG Ingestion Failure Analyzer
Triggered by CloudWatch alarm state changes for rag-ingest Lambda errors
Invokes central Lambda for AI agent analysis
"""

import json
import boto3
import os

# Configuration - set these as Lambda environment variables
AWS_REGION = os.environ.get('AWS_REGION', 'ap-southeast-1')
AGENT_REGION = os.environ.get('AGENT_REGION', 'ap-southeast-2')  # Where your rag-ingest Lambda runs
CENTRAL_LAMBDA_ARN = os.environ.get('CENTRAL_LAMBDA_ARN')  # Central analysis Lambda ARN


def get_recent_lambda_logs(function_name, limit=20):
    """Get latest Lambda logs from CloudWatch"""
    try:
        logs_client = boto3.client('logs', region_name=AGENT_REGION)
        log_group = f"/aws/lambda/{function_name}"

        # Get most recent log stream
        streams_response = logs_client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=1
        )

        if not streams_response['logStreams']:
            return ["No log streams found"]

        latest_stream = streams_response['logStreams'][0]

        # Get latest events from stream
        events_response = logs_client.get_log_events(
            logGroupName=log_group,
            logStreamName=latest_stream['logStreamName'],
            limit=limit,
            startFromHead=False  # Get most recent events
        )

        # Return the latest log messages
        messages = []
        for event in events_response['events']:
            message = event['message'].strip()
            if message:
                messages.append(message)

        return messages if messages else ["No log messages found"]

    except Exception as e:
        return [f"Failed to fetch logs: {str(e)}"]


def lambda_handler(event, context):
    """
    Handle CloudWatch Alarm event for RAG ingestion Lambda failures
    Transform event and invoke central Lambda for analysis

    Event format from CloudWatch Alarm via EventBridge:
    {
      "detail-type": "CloudWatch Alarm State Change",
      "detail": {
        "alarmName": "rag-ingest-errors",
        "state": {"value": "ALARM"},
        "configuration": {
          "description": "RAG Lambda errors"
        }
      }
    }
    """

    print(f"Received event: {json.dumps(event)}")

    try:
        # Parse CloudWatch Alarm event
        detail = event.get('detail', {})
        alarm_name = detail.get('alarmName', 'Unknown')
        alarm_state = detail.get('state', {}).get('value', 'UNKNOWN')

        # Extract Lambda function name (adjust based on your naming convention)
        function_name = 'rag-agent-system-ingest'  # Or extract from alarm name

        print(f"📊 Alarm: {alarm_name}")
        print(f"🚨 State: {alarm_state}")
        print(f"⚡ Lambda Function: {function_name}")

        # Get recent error logs
        print(f"📋 Fetching recent error logs...")
        error_logs = get_recent_lambda_logs(function_name, limit=10)

        print(f"📊 Fetched {len(error_logs)} log entries")
        if error_logs and error_logs[0].startswith("Failed to fetch"):
            print(f"⚠️ Log fetch failed: {error_logs[0]}")

        # Build additional context
        logs_summary = "\n".join(error_logs[:5]) if error_logs else "No recent error logs found"
        print(f"📝 Logs summary length: {len(logs_summary)} characters")

        context_info = {
            "aws_services": [
                f"Lambda Function: {function_name}",
                f"Region: {AGENT_REGION}",
                f"Log Group: /aws/lambda/{function_name}",
                "Bedrock Knowledge Base (RAG ingestion)",
                "S3 (trigger source)"
            ],
            "additional_info": f"""Recent Error Logs (last {len(error_logs[:5])} entries):
{logs_summary}

Context: This Lambda is triggered by S3 uploads and calls Bedrock Knowledge Base to start ingestion jobs.
Common issues: IAM permissions, Knowledge Base ID mismatch, S3 bucket access, file format issues."""
        }

        # Build standardized event for central Lambda
        central_event = {
            "service_name": function_name,
            "service_type": "Lambda",
            "error_details": f"Lambda function failure - Alarm: {alarm_name}, State: {alarm_state}",
            "issue_type": "lambda_errors",
            "severity": "high" if alarm_state == "ALARM" else "medium",
            "status": alarm_state,
            "context": context_info,
            "metadata": {
                "alarm_name": alarm_name,
                "function_region": AGENT_REGION,
                "log_entries_count": len(error_logs),
                "function_type": "rag-ingestion"
            }
        }

        # Validate central Lambda ARN
        if not CENTRAL_LAMBDA_ARN:
            print("❌ ERROR: CENTRAL_LAMBDA_ARN environment variable not set")
            return {
                'statusCode': 500,
                'body': json.dumps({'error': 'Central Lambda ARN not configured'})
            }

        # Log the context being sent
        print(f"📦 Context info being sent:")
        print(f"   - AWS Services: {len(context_info.get('aws_services', []))} items")
        print(f"   - Additional Info length: {len(context_info.get('additional_info', ''))} chars")

        # Invoke central Lambda
        print(f"🚀 Invoking central Lambda: {CENTRAL_LAMBDA_ARN}")
        lambda_client = boto3.client('lambda', region_name=AWS_REGION)

        response = lambda_client.invoke(
            FunctionName=CENTRAL_LAMBDA_ARN,
            InvocationType='Event',  # Async invocation - don't wait for response
            Payload=json.dumps(central_event)
        )

        print(f"✅ Central Lambda invoked successfully: StatusCode={response['StatusCode']}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'RAG failure event sent to central Lambda for analysis',
                'alarm': alarm_name,
                'function': function_name,
                'central_lambda_status': response['StatusCode'],
                'errors_found': len(error_logs)
            })
        }

    except Exception as e:
        print(f"❌ Error processing RAG failure alarm: {e}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
