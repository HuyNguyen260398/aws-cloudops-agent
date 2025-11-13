"""
Lambda function to process CloudWatch alarms and trigger agent notifications
"""

import json
import boto3
import os
from datetime import datetime


def lambda_handler(event, context):
    """Process SNS notification from CloudWatch alarm"""
    
    # Parse SNS message
    sns_message = json.loads(event['Records'][0]['Sns']['Message'])
    
    alarm_name = sns_message.get('AlarmName')
    new_state = sns_message.get('NewStateValue')
    reason = sns_message.get('NewStateReason')
    timestamp = sns_message.get('StateChangeTime')
    
    # Format alert message
    alert = {
        'timestamp': timestamp,
        'alarm_name': alarm_name,
        'state': new_state,
        'reason': reason,
        'severity': 'CRITICAL' if new_state == 'ALARM' else 'INFO'
    }
    
    # Option 1: Invoke your CloudOps Agent
    if os.environ.get('AGENT_ENDPOINT'):
        invoke_agent(alert)
    
    # Option 2: Send to Slack/Teams
    if os.environ.get('SLACK_WEBHOOK'):
        send_to_slack(alert)
    
    # Option 3: Store in DynamoDB for agent to query
    if os.environ.get('DYNAMODB_TABLE'):
        store_alert(alert)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Alert processed')
    }


def invoke_agent(alert):
    """Invoke CloudOps Agent with alert"""
    lambda_client = boto3.client('lambda')
    
    prompt = f"""
    🚨 ALERT DETECTED 🚨
    
    Alarm: {alert['alarm_name']}
    State: {alert['state']}
    Time: {alert['timestamp']}
    Reason: {alert['reason']}
    
    Please analyze this issue and provide recommendations.
    """
    
    lambda_client.invoke(
        FunctionName=os.environ['AGENT_ENDPOINT'],
        InvocationType='Event',
        Payload=json.dumps({'prompt': prompt})
    )


def send_to_slack(alert):
    """Send alert to Slack"""
    import urllib3
    http = urllib3.PoolManager()
    
    emoji = '🔴' if alert['severity'] == 'CRITICAL' else '🟡'
    
    message = {
        'text': f"{emoji} *{alert['alarm_name']}*",
        'attachments': [{
            'color': 'danger' if alert['severity'] == 'CRITICAL' else 'warning',
            'fields': [
                {'title': 'State', 'value': alert['state'], 'short': True},
                {'title': 'Time', 'value': alert['timestamp'], 'short': True},
                {'title': 'Reason', 'value': alert['reason'], 'short': False}
            ]
        }]
    }
    
    http.request(
        'POST',
        os.environ['SLACK_WEBHOOK'],
        body=json.dumps(message),
        headers={'Content-Type': 'application/json'}
    )


def store_alert(alert):
    """Store alert in DynamoDB"""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(os.environ['DYNAMODB_TABLE'])
    
    table.put_item(
        Item={
            'alert_id': f"{alert['alarm_name']}-{alert['timestamp']}",
            'timestamp': alert['timestamp'],
            'alarm_name': alert['alarm_name'],
            'state': alert['state'],
            'reason': alert['reason'],
            'severity': alert['severity'],
            'processed': False
        }
    )
