# 🚀 Feature: Slack Approval Workflow for Domain Monitoring

## Overview

This feature adds an interactive Slack approval workflow to the domain monitoring system. When a domain goes down and the AI agent analyzes the issue, users receive a beautiful Slack card with an "Approve" button to review and execute automated remediation actions with a single click.

## 📋 What Was Implemented

### 1. Enhanced Domain Monitoring Lambda
**File**: `src/ops/lambda_ping_monitor.py`

**New Capabilities**:
- Generates unique alert IDs for each incident
- Stores alert data in DynamoDB with automatic 24-hour expiration (TTL)
- Sends rich Slack cards with interactive approval buttons
- Integrates with DynamoDB for approval workflow tracking

**Key Functions Added**:
```python
store_alert_data(alert_id, domain, status, timestamp, error_details, agent_analysis)
# Stores alert information in DynamoDB for the approval workflow

send_slack_notification(domain, status, timestamp, agent_analysis, alert_id)
# Enhanced to include interactive buttons and alert ID
```

### 2. Slack Approval Handler Lambda
**File**: `src/ops/lambda_approval_handler.py` (NEW)

**Capabilities**:
- Receives and validates Slack interactive button callbacks
- Verifies request signatures using HMAC-SHA256 for security
- Retrieves alert data from DynamoDB
- Executes automated remediation actions when approved
- Updates Slack messages with remediation results
- Prevents duplicate approvals

**Remediation Actions**:
- ✅ CloudFront cache invalidation
- ✅ Route53 health check verification
- ✅ SNS notifications for remediation results
- ✅ Extensible architecture for custom actions

**Key Functions**:
```python
verify_slack_signature(event)
# Validates that requests came from Slack

execute_remediation_actions(alert_data)
# Performs automated remediation based on alert context

update_slack_message(response_url, alert_data, action, user_name, remediation_results)
# Updates the original Slack message with results
```

### 3. CloudFormation Infrastructure
**File**: `cloudformation/ping-monitor-with-approval.yaml` (NEW)

**Resources Created**:
- **DynamoDB Table**: Stores alert data with TTL for automatic cleanup
- **API Gateway**: HTTP API endpoint for Slack callbacks
- **Lambda Functions**: Both monitor and approval handler
- **IAM Roles**: Least-privilege permissions for each function
- **SNS Topics**: Email alerts + remediation notifications
- **CloudWatch Events**: Scheduled monitoring trigger
- **CloudWatch Logs**: Automatic log retention

**Key Features**:
- Complete infrastructure-as-code
- Configurable parameters for easy customization
- Secure by default with proper IAM policies
- Cost-optimized with pay-per-use resources

### 4. Deployment Automation
**File**: `deploy-approval-workflow.ps1` (NEW)

**Features**:
- One-command deployment
- Automatic CloudFormation stack creation/update
- Lambda function packaging and deployment
- Clear instructions for Slack app configuration
- Validation and error handling

**Usage**:
```powershell
.\deploy-approval-workflow.ps1 `
  -StackName "domain-monitor-approval" `
  -SlackWebhookURL "https://hooks.slack.com/services/YOUR/WEBHOOK" `
  -SlackSigningSecret "your_signing_secret" `
  -EmailAddress "alerts@yourcompany.com"
```

### 5. Testing Tools
**File**: `test-approval-workflow.ps1` (NEW)

**Capabilities**:
- Manual Lambda invocation for testing
- DynamoDB alert inspection
- CloudWatch log queries
- Troubleshooting guidance

## 🎯 How It Works

### Workflow Sequence

```
1. CloudWatch Events → Triggers Lambda every 5 minutes
2. Ping Monitor Lambda → Checks domain availability
3. If DOWN:
   a. Generate unique alert ID
   b. Invoke AI agent for analysis
   c. Store alert data in DynamoDB
   d. Send Slack card with buttons
   e. Send email via SNS
4. User in Slack → Clicks "Approve & Execute" button
5. Slack → Sends callback to API Gateway
6. API Gateway → Invokes Approval Handler Lambda
7. Approval Handler:
   a. Verify Slack signature
   b. Retrieve alert from DynamoDB
   c. Execute remediation actions
   d. Update DynamoDB status
   e. Update Slack message with results
```

### Example Slack Card

```
╔═══════════════════════════════════════════╗
║  🚨 ALERT: Domain Alert - nghuy.link      ║
╠═══════════════════════════════════════════╣
║  Domain: nghuy.link                       ║
║  Status: DOWN                             ║
║  Timestamp: 2025-11-22 10:30:00           ║
║  Alert ID: 550e8400-e29b-41d4-a716...     ║
╟───────────────────────────────────────────╢
║  🤖 AI Agent Analysis:                    ║
║                                           ║
║  ROOT CAUSE: CloudFront distribution      ║
║  returning 503 errors. Origin health      ║
║  checks failing.                          ║
║                                           ║
║  RECOMMENDED ACTIONS:                     ║
║  1. Invalidate CloudFront cache           ║
║  2. Check S3 bucket availability          ║
║  3. Verify Route53 health checks          ║
╟───────────────────────────────────────────╢
║  [✅ Approve & Execute]  [❌ Dismiss]     ║
╚═══════════════════════════════════════════╝
```

After approval, the card updates to show:

```
╔═══════════════════════════════════════════╗
║  ✅ RESOLVED: Domain Alert - nghuy.link   ║
╠═══════════════════════════════════════════╣
║  Status: RESOLVING                        ║
║  Approved By: john.doe @ 10:35:00         ║
╟───────────────────────────────────────────╢
║  🔧 Remediation Actions Executed:         ║
║  ✅ CloudFront Cache Invalidation         ║
║  ✅ Route53 Health Check Verified         ║
║  ✅ Remediation Report Sent               ║
╚═══════════════════════════════════════════╝
```

## 🔒 Security Features

### 1. Slack Signature Verification
- All Slack requests verified using HMAC-SHA256
- Timestamp validation prevents replay attacks (5-minute window)
- Rejects unauthorized requests

### 2. IAM Least Privilege
- Each Lambda has minimal required permissions
- No wildcard permissions
- Scoped to specific resources

### 3. Data Protection
- DynamoDB TTL auto-expires alerts after 24 hours
- No long-term storage of sensitive data
- Audit trail in CloudWatch Logs

### 4. API Gateway
- HTTPS only
- Can add rate limiting
- Can integrate with AWS WAF

## 📊 Cost Analysis

### Monthly Cost Breakdown (5-minute monitoring interval)

| Service | Usage | Free Tier | Paid Cost | After Free Tier |
|---------|-------|-----------|-----------|-----------------|
| Lambda (Monitor) | 8,640 invokes | 1M requests | $0.20 | $0.00 |
| Lambda (Approval) | ~10 invokes | 1M requests | $0.01 | $0.00 |
| DynamoDB | On-demand | 25 GB | $0.25 | $0.00 |
| API Gateway | ~10 requests | 1M requests | $0.10 | $0.00 |
| CloudWatch Logs | 100 MB | 5 GB | $0.50 | $0.00 |
| SNS | 10 emails | 1,000 | $0.01 | $0.00 |
| **Total** | | | **$1.07** | **$0.00** |

**Conclusion**: With AWS Free Tier, this solution costs **$0/month** for the first year. After free tier, approximately **$1.07/month**.

## 🚀 Quick Start

### Prerequisites
1. AWS Account with CLI configured
2. Slack workspace with admin access
3. PowerShell 5.1+ (for deployment scripts)

### Step 1: Create Slack App
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "Domain Monitor Bot"
4. Select your workspace
5. Navigate to "Incoming Webhooks" → Enable → Add webhook
6. Copy the webhook URL
7. Navigate to "Basic Information" → Copy "Signing Secret"

### Step 2: Deploy Infrastructure
```powershell
cd C:\Workspace\AwsCloudOpsAgent

.\deploy-approval-workflow.ps1 `
  -StackName "domain-monitor-approval" `
  -SlackWebhookURL "https://hooks.slack.com/services/T.../B.../..." `
  -SlackSigningSecret "abc123..." `
  -EmailAddress "your-email@example.com" `
  -DomainName "yoursite.com"
```

### Step 3: Configure Slack Interactivity
1. Note the API endpoint URL from deployment output
2. In Slack app settings → "Interactivity & Shortcuts"
3. Enable Interactivity
4. Paste the API endpoint as Request URL
5. Save Changes

### Step 4: Test
```powershell
.\test-approval-workflow.ps1 -StackName "domain-monitor-approval"
```

Check your Slack channel for the alert card!

## 📚 Documentation

### Complete Documentation
- **Full Guide**: `docs/SLACK_APPROVAL_WORKFLOW.md`
- **Quick Start**: `docs/SLACK_APPROVAL_QUICKSTART.md`
- **Visual Diagrams**: `docs/SLACK_APPROVAL_DIAGRAMS.md`
- **Implementation Summary**: `docs/SLACK_APPROVAL_SUMMARY.md`
- **Example Data**: `src/ops/example_approval_workflow.py`

### Key Configuration

#### Environment Variables (Ping Monitor)
```
DOMAIN_NAME                 - Domain to monitor
SNS_TOPIC_ARN              - SNS topic for email alerts
SLACK_WEBHOOK_URL          - Slack webhook URL
DYNAMODB_ALERTS_TABLE      - DynamoDB table name
AGENT_RUNTIME_ARN          - Bedrock agent ARN (optional)
COGNITO_USERNAME           - Cognito username (optional)
COGNITO_PASSWORD           - Cognito password (optional)
COGNITO_CLIENT_ID          - Cognito client ID (optional)
CLOUDFRONT_DISTRIBUTION_ID - CloudFront ID (optional)
```

#### Environment Variables (Approval Handler)
```
DYNAMODB_ALERTS_TABLE      - DynamoDB table name
SLACK_SIGNING_SECRET       - Slack signing secret
REMEDIATION_SNS_TOPIC_ARN  - SNS for remediation notifications
CLOUDFRONT_DISTRIBUTION_ID - CloudFront ID (optional)
```

## 🎨 Customization

### Adding Custom Remediation Actions

Edit `src/ops/lambda_approval_handler.py`:

```python
def execute_remediation_actions(alert_data):
    """Execute automated remediation actions"""
    
    # Example: Restart ECS service
    ecs = boto3.client('ecs')
    ecs.update_service(
        cluster='my-cluster',
        service='my-service',
        forceNewDeployment=True
    )
    
    remediation_results.append({
        "action": "ECS Service Restart",
        "status": "success",
        "details": "Service redeployed successfully"
    })
    
    # Example: Update Auto Scaling
    autoscaling = boto3.client('autoscaling')
    autoscaling.set_desired_capacity(
        AutoScalingGroupName='my-asg',
        DesiredCapacity=5
    )
    
    remediation_results.append({
        "action": "Auto Scaling Update",
        "status": "success",
        "details": "Scaled to 5 instances"
    })
    
    return remediation_results
```

### Monitoring Multiple Domains

Modify `src/ops/lambda_ping_monitor.py`:

```python
def lambda_handler(event, context):
    domains = ["site1.com", "site2.com", "site3.com"]
    results = []
    
    for domain in domains:
        # Check each domain independently
        result = check_domain(domain)
        results.append(result)
    
    return {"statusCode": 200, "results": results}
```

### Change Monitoring Frequency

Update CloudFormation parameter:
```powershell
-MonitoringSchedule "rate(1 minute)"   # Every minute
-MonitoringSchedule "rate(10 minutes)" # Every 10 minutes
-MonitoringSchedule "cron(0 * * * ? *)" # Every hour at :00
```

## 🔍 Troubleshooting

### Slack Button Doesn't Work
1. Verify API Gateway endpoint in Slack app settings
2. Check Slack signing secret is correct
3. Review Lambda execution logs: `aws logs tail /aws/lambda/STACK-NAME-approval-handler --follow`
4. Ensure API Gateway has permission to invoke Lambda

### Remediation Not Executing
1. Check IAM role permissions for approval handler
2. Verify CloudFront distribution ID (if using)
3. Review CloudWatch logs for errors
4. Ensure alert exists in DynamoDB

### Messages Not Appearing in Slack
1. Verify Slack webhook URL is correct
2. Check Lambda has internet connectivity
3. Review CloudWatch logs for HTTP errors
4. Test webhook manually with curl

### Common Error Codes
- **401 Unauthorized**: Invalid Slack signature
- **404 Not Found**: Alert ID not in DynamoDB or expired
- **500 Internal Server Error**: Lambda execution error (check logs)

## 📈 Monitoring & Observability

### CloudWatch Metrics to Monitor
- Lambda invocation count & errors
- API Gateway latency & 4xx/5xx errors
- DynamoDB read/write capacity
- SNS publish success/failure

### Recommended CloudWatch Alarms
```yaml
# Lambda errors > 5% in 5 minutes
# API Gateway 5xx > 3 in 5 minutes
# DynamoDB throttling events
# SNS publish failures
```

### Log Insights Queries

**Find failed approvals:**
```sql
fields @timestamp, alert_id, error
| filter @message like /Error processing approval/
| sort @timestamp desc
| limit 20
```

**Track remediation actions:**
```sql
fields @timestamp, alert_id, remediation_results
| filter @message like /Remediation Actions Executed/
| sort @timestamp desc
| limit 20
```

## 🎯 Future Enhancements

Potential improvements for future iterations:

1. **Multi-Approval Workflow**: Require approval from multiple users
2. **Approval Chains**: Different approval levels based on severity
3. **Slack Threads**: Keep conversations organized in threads
4. **Dashboard**: Real-time monitoring dashboard with metrics
5. **ML Predictions**: Predict issues before they occur
6. **Integration**: PagerDuty, Jira, ServiceNow integration
7. **Multi-Region**: Deploy across regions for high availability
8. **Custom Alerts**: Per-domain custom remediation workflows
9. **Rollback**: Automatic rollback if remediation fails
10. **Approval History**: View past approvals and outcomes

## 🤝 Contributing

To extend this feature:

1. Test changes locally with `test-approval-workflow.ps1`
2. Update CloudFormation template if infrastructure changes
3. Document new environment variables
4. Add examples to documentation
5. Test Slack integration thoroughly

## 📝 Change Log

### Version 1.0.0 (2025-11-22)
- ✅ Initial implementation
- ✅ Slack interactive button support
- ✅ DynamoDB alert storage with TTL
- ✅ API Gateway integration
- ✅ Automated remediation actions
- ✅ Complete CloudFormation infrastructure
- ✅ Deployment automation scripts
- ✅ Comprehensive documentation

## 📞 Support

For issues or questions:
1. Check documentation in `docs/` folder
2. Review CloudWatch logs for errors
3. Test with `test-approval-workflow.ps1`
4. Verify environment variables are set
5. Check Slack app configuration

---

**Built with** ❤️ **for AWS CloudOps automation**

Last Updated: November 22, 2025
