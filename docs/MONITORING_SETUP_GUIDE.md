# 🔔 Website Monitoring Setup Guide

Complete guide to set up automated monitoring and notifications for your AWS static website.

## 📋 Overview

This guide helps you set up a monitoring workflow that:
- Monitors CloudFront, WAF, Route 53, and S3
- Sends alerts via SNS (Email/SMS)
- Optionally triggers your CloudOps Agent for automated analysis
- Integrates with Slack/Teams for team notifications

## 🏗️ Architecture

```
CloudWatch Alarms → SNS Topic → Lambda Function → Multiple Outputs:
                                                   ├─ Email/SMS
                                                   ├─ CloudOps Agent
                                                   ├─ Slack/Teams
                                                   └─ DynamoDB (Alert History)
```

## 🚀 Quick Setup

### Step 1: Configure Your Settings

Edit the configuration in `src/monitoring/website_monitor_setup.py`:

```python
config = {
    'topic_name': 'website-monitoring-alerts',
    'email': 'your-email@example.com',
    'cloudfront_distribution_id': 'E1234EXAMPLE',  # Get from CloudFront console
    'waf_web_acl_name': 'your-web-acl',            # Get from WAF console
    'domain': 'example.com',                        # Your website domain
    'region': 'us-east-1'
}
```

### Step 2: Run Setup Script

```bash
cd c:\Workspace\AwsCloudOpsAgent
uv run src/monitoring/website_monitor_setup.py
```

### Step 3: Confirm Email Subscription

Check your email and confirm the SNS subscription.

## 📊 What Gets Monitored

### CloudFront Metrics
- **5xx Error Rate**: Alerts when > 5% (server errors)
- **4xx Error Rate**: Alerts when > 10% (client errors)
- **Cache Hit Rate**: Alerts when < 70% (performance issue)

### WAF Metrics
- **Blocked Requests Spike**: Alerts when > 1000 (potential attack)
- **Allowed Requests Drop**: Alerts when < 10 (service issue)

### Route 53 Health Checks
- **Endpoint Availability**: Checks every 30 seconds
- **Latency Monitoring**: Tracks response times
- **Failure Threshold**: 3 consecutive failures trigger alert

### Certificate Manager
- **Expiration Warning**: 30 days before expiry (manual setup)

## 🔧 Advanced Setup: Agent Integration

### Option 1: Lambda Handler for Agent Notifications

Deploy the Lambda function to process alerts:

```bash
# Package Lambda function
cd src/monitoring
zip -r lambda_function.zip agent_notification_handler.py

# Create Lambda function
aws lambda create-function \
  --function-name website-alert-processor \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --handler agent_notification_handler.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --environment Variables="{AGENT_ENDPOINT=your-agent-function}"
```

### Option 2: Subscribe Lambda to SNS

```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:REGION:ACCOUNT:website-monitoring-alerts \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:REGION:ACCOUNT:function:website-alert-processor
```

## 📱 Notification Channels

### Email/SMS (Built-in)
Already configured via SNS subscription.

### Slack Integration

1. Create Slack webhook: https://api.slack.com/messaging/webhooks
2. Add to Lambda environment:
```bash
aws lambda update-function-configuration \
  --function-name website-alert-processor \
  --environment Variables="{SLACK_WEBHOOK=https://hooks.slack.com/services/YOUR/WEBHOOK/URL}"
```

### Microsoft Teams Integration

Similar to Slack, use Teams webhook connector.

## 🎯 Testing Your Setup

### Test CloudWatch Alarm

```bash
# Manually set alarm to ALARM state
aws cloudwatch set-alarm-state \
  --alarm-name "CloudFront-5xx-Errors-E1234EXAMPLE" \
  --state-value ALARM \
  --state-reason "Testing alert system"
```

### Test Route 53 Health Check

```bash
# Get health check status
aws route53 get-health-check-status \
  --health-check-id YOUR_HEALTH_CHECK_ID
```

## 📈 Monitoring Dashboard

Create a CloudWatch Dashboard to visualize all metrics:

```python
from website_monitor_setup import WebsiteMonitorSetup

monitor = WebsiteMonitorSetup()

# Dashboard will be created automatically with all metrics
dashboard_body = {
    "widgets": [
        {
            "type": "metric",
            "properties": {
                "metrics": [
                    ["AWS/CloudFront", "5xxErrorRate", {"stat": "Average"}],
                    [".", "4xxErrorRate", {"stat": "Average"}],
                    [".", "CacheHitRate", {"stat": "Average"}]
                ],
                "period": 300,
                "stat": "Average",
                "region": "us-east-1",
                "title": "CloudFront Health"
            }
        }
    ]
}
```

## 🔍 Troubleshooting

### No Alerts Received

1. Check SNS subscription is confirmed
2. Verify CloudWatch alarms are enabled
3. Check alarm thresholds are appropriate
4. Review CloudWatch Logs for Lambda errors

### False Positives

Adjust alarm thresholds in `website_monitor_setup.py`:

```python
# Example: Increase 5xx error threshold
'threshold': 10.0,  # Changed from 5.0
```

### Lambda Not Triggering

1. Check Lambda execution role has SNS permissions
2. Verify SNS subscription to Lambda is active
3. Check Lambda CloudWatch Logs

## 💰 Cost Estimate

- CloudWatch Alarms: $0.10/alarm/month (~$0.50/month for 5 alarms)
- Route 53 Health Check: $0.50/month
- SNS: $0.50/month (first 1,000 emails free)
- Lambda: Free tier covers most usage
- **Total: ~$1.50-2.00/month**

## 🔐 Security Best Practices

1. Use IAM roles with least privilege
2. Encrypt SNS topics with KMS
3. Enable CloudTrail for audit logging
4. Restrict Lambda execution role permissions
5. Use VPC endpoints for private communication

## 📚 Additional Resources

- [CloudWatch Alarms Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
- [Route 53 Health Checks](https://docs.aws.amazon.com/Route53/latest/DeveloperGuide/health-checks-creating.html)
- [SNS Best Practices](https://docs.aws.amazon.com/sns/latest/dg/sns-best-practices.html)

## 🎓 Next Steps

1. Set up custom metrics for business KPIs
2. Create runbooks for common issues
3. Integrate with incident management tools (PagerDuty, Opsgenie)
4. Set up automated remediation with Systems Manager
5. Create weekly/monthly reports with CloudWatch Insights
