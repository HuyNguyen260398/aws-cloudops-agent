# Lambda Functions Deployment Guide

## Overview

This guide covers the deployment and configuration of the 3-phase AWS CloudOps Agent workflow:

1. **lambda_invoke_handler.py** - Detection & Analysis
2. **lambda_approval_handler.py** - Approval Workflow
3. **lambda_execution_handler.py** - Execution with Context Retention

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    AWS CloudOps Agent Workflow                   │
└─────────────────────────────────────────────────────────────────┘

Phase 1: Detection & Analysis
┌──────────────┐
│ EventBridge  │
│ (Schedule)   │
└──────┬───────┘
       │ Trigger every 5 minutes
       ↓
┌─────────────────────────────┐
│ lambda_invoke_handler       │
│ - Detect domain issues      │
│ - Invoke Bedrock Agent      │
│ - Summarize analysis        │
│ - Upload to S3              │
│ - Store in DynamoDB         │
│ - Send to Teams/Slack       │
└─────────────┬───────────────┘
              │
              ↓
┌─────────────────────────────┐
│ DynamoDB: alerts            │
│ Status: pending             │
│ agent_session_id: xyz       │
└─────────────────────────────┘

Phase 2: Approval
┌──────────────────────┐
│ Teams/Slack          │
│ Adaptive Card        │
│ [Approve] [Reject]   │
└─────────┬────────────┘
          │ User clicks button
          ↓
┌─────────────────────────────┐
│ API Gateway                 │
│ /approval                   │
└─────────┬───────────────────┘
          │
          ↓
┌─────────────────────────────┐
│ lambda_approval_handler     │
│ - Validate request          │
│ - Update DynamoDB           │
│ - Trigger execution (SNS)   │
│ - Send confirmation         │
└─────────────┬───────────────┘
              │ If approved
              ↓
┌─────────────────────────────┐
│ SNS Topic                   │
│ execution-trigger           │
└─────────────────────────────┘

Phase 3: Execution
┌─────────────────────────────┐
│ SNS Trigger                 │
└─────────┬───────────────────┘
          │
          ↓
┌─────────────────────────────┐
│ lambda_execution_handler    │
│ - Get alert from DynamoDB   │
│ - Get analysis from S3      │
│ - Invoke agent with         │
│   session_id (context!)     │
│ - Execute recommendations   │
│ - Log all actions           │
│ - Upload execution log      │
│ - Send notifications        │
└─────────────────────────────┘
```

---

## Lambda Function 1: Analysis Handler

**File:** `src/lambdas/lambda_invoke_handler.py`

### Purpose
- Scheduled detection of domain issues
- AI-powered analysis using Bedrock Agent
- Multi-channel notifications with approval buttons

### Configuration

#### Runtime
- Python 3.11 or higher
- Memory: 512 MB
- Timeout: 5 minutes (300 seconds)

#### Environment Variables
```bash
# Required
AGENT_RUNTIME_ARN=arn:aws:bedrock:us-east-1:xxxxx:agent/agent-id/alias/alias-id
COGNITO_USERNAME=ted8hc
COGNITO_PASSWORD=<secure-password>
COGNITO_CLIENT_ID=<cognito-client-id>
S3_ANALYSIS_BUCKET=domain-alert-analysis
DYNAMODB_ALERTS_TABLE=alerts

# Optional (Notifications)
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:xxxxx:cloudops-alerts
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...

# For Approval
APPROVAL_API_URL=https://api.example.com/approval
```

#### IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAgent",
        "bedrock:GetAgent"
      ],
      "Resource": "arn:aws:bedrock:*:*:agent/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::domain-alert-analysis/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/alerts"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:*:*:cloudops-alerts"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

#### Trigger
EventBridge Rule (cron expression):
```
rate(5 minutes)
```

Or EventBridge schedule:
```json
{
  "scheduleExpression": "rate(5 minutes)",
  "state": "ENABLED"
}
```

---

## Lambda Function 2: Approval Handler

**File:** `src/ops/lambda_approval_handler.py`

### Purpose
- Handle approval/rejection actions from users
- Update DynamoDB status
- Trigger execution Lambda via SNS

### Configuration

#### Runtime
- Python 3.11 or higher
- Memory: 256 MB
- Timeout: 30 seconds

#### Environment Variables
```bash
# Required
DYNAMODB_ALERTS_TABLE=alerts
EXECUTION_TRIGGER_SNS=arn:aws:sns:us-east-1:xxxxx:execution-trigger

# Optional (Notifications)
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:xxxxx:cloudops-alerts
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

#### IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/alerts"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": [
        "arn:aws:sns:*:*:execution-trigger",
        "arn:aws:sns:*:*:cloudops-alerts"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

#### Trigger
API Gateway REST API:
- Method: POST
- Path: `/approval`
- Query parameters: `alert_id`, `action`, `approved_by`, `comment`

Example API Gateway integration:
```yaml
/approval:
  post:
    x-amazon-apigateway-integration:
      type: aws_proxy
      httpMethod: POST
      uri: arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:xxxxx:function:approval-handler/invocations
```

---

## Lambda Function 3: Execution Handler

**File:** `src/ops/lambda_execution_handler.py`

### Purpose
- Execute agent recommendations after approval
- Maintain conversation context via session_id
- Log all actions and results

### Configuration

#### Runtime
- Python 3.11 or higher
- Memory: 1024 MB
- Timeout: 15 minutes (900 seconds)

#### Environment Variables
```bash
# Required
AGENT_RUNTIME_ARN=arn:aws:bedrock:us-east-1:xxxxx:agent/agent-id/alias/alias-id
COGNITO_USERNAME=ted8hc
COGNITO_PASSWORD=<secure-password>
COGNITO_CLIENT_ID=<cognito-client-id>
S3_ANALYSIS_BUCKET=domain-alert-analysis
DYNAMODB_ALERTS_TABLE=alerts

# Optional (Notifications)
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:xxxxx:cloudops-alerts
TEAMS_WEBHOOK_URL=https://outlook.office.com/webhook/...
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

#### IAM Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeAgent",
        "bedrock:GetAgent"
      ],
      "Resource": "arn:aws:bedrock:*:*:agent/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject"
      ],
      "Resource": "arn:aws:s3:::domain-alert-analysis/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/alerts"
    },
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": "arn:aws:sns:*:*:cloudops-alerts"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateInvalidation",
        "route53:GetHealthCheck",
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    }
  ]
}
```

#### Trigger
SNS Topic: `execution-trigger`

SNS subscription:
```bash
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:xxxxx:execution-trigger \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:us-east-1:xxxxx:function:execution-handler
```

---

## DynamoDB Table Schema

**Table Name:** `alerts`

### Primary Key
- **alert_id** (String) - Partition Key

### Attributes
```
alert_id: String (PK)
domain: String
timestamp: String (ISO 8601)
approval_status: String (pending|approved|rejected)
agent_analysis: String (full analysis text)
agent_session_id: String (for context retention)
s3_analysis_key: String
s3_analysis_url: String
approved_by: String
approved_at: String
rejected_by: String
rejected_at: String
approval_comment: String
rejection_reason: String
execution_status: String (not_started|in_progress|completed|failed)
executed_at: String
execution_log: String
execution_details: String (JSON)
ttl: Number (Unix timestamp, auto-expires after 30 days)
```

### TTL Configuration
Enable TTL on `ttl` attribute to auto-delete old alerts after 30 days.

### Create Table
```bash
aws dynamodb create-table \
  --table-name alerts \
  --attribute-definitions \
    AttributeName=alert_id,AttributeType=S \
  --key-schema \
    AttributeName=alert_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --tags Key=Project,Value=CloudOpsAgent

# Enable TTL
aws dynamodb update-time-to-live \
  --table-name alerts \
  --time-to-live-specification Enabled=true,AttributeName=ttl
```

---

## S3 Bucket Setup

**Bucket Name:** `domain-alert-analysis`

### Folder Structure
```
domain-alert-analysis/
├── alerts/
│   └── YYYY-MM-DD/
│       └── domain/
│           └── HH-MM-SS-alert_id.md
└── executions/
    └── YYYY-MM-DD/
        └── domain/
            └── HH-MM-SS-alert_id.md
```

### Create Bucket
```bash
aws s3 mb s3://domain-alert-analysis

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket domain-alert-analysis \
  --versioning-configuration Status=Enabled

# Set lifecycle policy (optional - delete after 90 days)
cat > lifecycle.json <<EOF
{
  "Rules": [
    {
      "Id": "DeleteOldAnalysis",
      "Status": "Enabled",
      "Prefix": "",
      "Expiration": {
        "Days": 90
      }
    }
  ]
}
EOF

aws s3api put-bucket-lifecycle-configuration \
  --bucket domain-alert-analysis \
  --lifecycle-configuration file://lifecycle.json
```

---

## SNS Topics

### Topic 1: cloudops-alerts
For general notifications to operations team.

```bash
aws sns create-topic --name cloudops-alerts

# Subscribe email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:xxxxx:cloudops-alerts \
  --protocol email \
  --notification-endpoint ops-team@example.com
```

### Topic 2: execution-trigger
For triggering execution Lambda after approval.

```bash
aws sns create-topic --name execution-trigger

# Subscribe Lambda
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:xxxxx:execution-trigger \
  --protocol lambda \
  --notification-endpoint arn:aws:lambda:us-east-1:xxxxx:function:execution-handler

# Grant SNS permission to invoke Lambda
aws lambda add-permission \
  --function-name execution-handler \
  --statement-id sns-invoke \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn arn:aws:sns:us-east-1:xxxxx:execution-trigger
```

---

## API Gateway Setup

### Create REST API
```bash
aws apigateway create-rest-api \
  --name cloudops-approval-api \
  --description "API for CloudOps approval workflow"
```

### Create Resource
```bash
# Get API ID
API_ID=$(aws apigateway get-rest-apis --query "items[?name=='cloudops-approval-api'].id" --output text)

# Get root resource ID
ROOT_ID=$(aws apigateway get-resources --rest-api-id $API_ID --query "items[?path=='/'].id" --output text)

# Create /approval resource
aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part approval
```

### Create Method
```bash
RESOURCE_ID=$(aws apigateway get-resources --rest-api-id $API_ID --query "items[?path=='/approval'].id" --output text)

# Create POST method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --authorization-type NONE

# Set up Lambda integration
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:xxxxx:function:approval-handler/invocations

# Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
  --function-name approval-handler \
  --statement-id apigateway-invoke \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:us-east-1:xxxxx:$API_ID/*/POST/approval"
```

### Deploy API
```bash
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod
```

### Get API URL
```bash
echo "https://$API_ID.execute-api.us-east-1.amazonaws.com/prod/approval"
```

---

## Deployment Steps

### 1. Package Lambda Functions

For each Lambda function:

```bash
# Create deployment package
cd src/lambdas
zip -r ../../lambda_invoke_handler.zip lambda_invoke_handler.py
cd ../components
zip -r ../../lambda_invoke_handler.zip auth.py
cd ../utils
zip -r ../../lambda_invoke_handler.zip mylogger.py
cd ../../

# Upload to S3
aws s3 cp lambda_invoke_handler.zip s3://my-lambda-deployments/

# Create/Update Lambda
aws lambda create-function \
  --function-name invoke-agent-analysis \
  --runtime python3.11 \
  --role arn:aws:iam::xxxxx:role/lambda-execution-role \
  --handler lambda_invoke_handler.lambda_handler \
  --code S3Bucket=my-lambda-deployments,S3Key=lambda_invoke_handler.zip \
  --timeout 300 \
  --memory-size 512 \
  --environment Variables="{AGENT_RUNTIME_ARN=...,COGNITO_USERNAME=...}"
```

### 2. Create DynamoDB Table
```bash
aws dynamodb create-table \
  --table-name alerts \
  --attribute-definitions AttributeName=alert_id,AttributeType=S \
  --key-schema AttributeName=alert_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

### 3. Create S3 Bucket
```bash
aws s3 mb s3://domain-alert-analysis
```

### 4. Create SNS Topics
```bash
aws sns create-topic --name cloudops-alerts
aws sns create-topic --name execution-trigger
```

### 5. Set Up API Gateway
Follow the API Gateway setup steps above.

### 6. Configure EventBridge
```bash
aws events put-rule \
  --name cloudops-analysis-schedule \
  --schedule-expression "rate(5 minutes)"

aws events put-targets \
  --rule cloudops-analysis-schedule \
  --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:xxxxx:function:invoke-agent-analysis"

aws lambda add-permission \
  --function-name invoke-agent-analysis \
  --statement-id eventbridge-invoke \
  --action lambda:InvokeFunction \
  --principal events.amazonaws.com \
  --source-arn arn:aws:events:us-east-1:xxxxx:rule/cloudops-analysis-schedule
```

---

## Testing

### Test Analysis Lambda
```bash
aws lambda invoke \
  --function-name invoke-agent-analysis \
  --payload '{}' \
  response.json

cat response.json
```

### Test Approval Lambda
```bash
aws lambda invoke \
  --function-name approval-handler \
  --payload '{"alert_id":"test-123","action":"approve","approved_by":"testuser"}' \
  response.json
```

### Test Execution Lambda
```bash
aws lambda invoke \
  --function-name execution-handler \
  --payload '{"alert_id":"test-123"}' \
  response.json
```

---

## Monitoring

### CloudWatch Metrics
- Lambda invocations
- Lambda errors
- Lambda duration
- DynamoDB read/write capacity
- S3 requests

### CloudWatch Alarms
```bash
# Lambda errors
aws cloudwatch put-metric-alarm \
  --alarm-name lambda-analysis-errors \
  --alarm-description "Alert when analysis Lambda has errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=invoke-agent-analysis
```

### Logs Insights Queries

**Analysis Performance:**
```
fields @timestamp, @message
| filter @message like /Analysis completed/
| stats count() as invocations, avg(@duration) as avg_duration
```

**Approval Rate:**
```
fields @timestamp, approval_status
| filter @message like /approved/ or @message like /rejected/
| stats count() by approval_status
```

**Execution Success Rate:**
```
fields @timestamp, execution_status
| filter @message like /Execution completed/ or @message like /Execution failed/
| stats count() by execution_status
```

---

## Security Best Practices

### 1. Secrets Management
Store sensitive credentials in AWS Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name cloudops/cognito-credentials \
  --secret-string '{"username":"ted8hc","password":"<secure-password>"}'
```

Update Lambda to retrieve from Secrets Manager:
```python
import boto3
import json

def get_cognito_credentials():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='cloudops/cognito-credentials')
    credentials = json.loads(response['SecretString'])
    return credentials['username'], credentials['password']
```

### 2. API Gateway Authentication
Add API key or IAM authentication:

```bash
# Create API key
aws apigateway create-api-key \
  --name cloudops-approval-key \
  --enabled

# Create usage plan
aws apigateway create-usage-plan \
  --name cloudops-approval-plan \
  --api-stages apiId=$API_ID,stage=prod
```

### 3. DynamoDB Encryption
Enable encryption at rest:

```bash
aws dynamodb update-table \
  --table-name alerts \
  --sse-specification Enabled=true,SSEType=KMS
```

### 4. S3 Bucket Policy
Restrict access to Lambda execution role only:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::xxxxx:role/lambda-execution-role"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::domain-alert-analysis/*"
    }
  ]
}
```

---

## Troubleshooting

### Common Issues

#### 1. Cognito Authentication Fails
**Error:** `Invalid credentials`

**Solution:**
- Verify COGNITO_USERNAME, COGNITO_PASSWORD, COGNITO_CLIENT_ID
- Check Cognito user exists and is confirmed
- Ensure user pool allows password authentication

#### 2. Agent Session Not Found
**Error:** `Session not found`

**Solution:**
- Verify agent_session_id is stored in DynamoDB
- Check session hasn't expired (default 1 hour)
- Ensure same session_id is used for analysis and execution

#### 3. S3 Upload Fails
**Error:** `Access Denied`

**Solution:**
- Verify Lambda has `s3:PutObject` permission
- Check bucket name is correct
- Ensure bucket policy allows Lambda role

#### 4. DynamoDB Update Fails
**Error:** `ResourceNotFoundException`

**Solution:**
- Verify table name is correct
- Check table exists in correct region
- Ensure Lambda has DynamoDB permissions

#### 5. Teams/Slack Notification Fails
**Error:** `Invalid webhook URL`

**Solution:**
- Verify webhook URL is correct and active
- Test webhook manually with curl
- Check message format follows Teams/Slack schema

---

## Cost Estimation

### Monthly Costs (Estimated)

**Assumptions:**
- 5-minute interval = 288 invocations/day = 8,640/month
- 50% alerts require approval
- 80% of approvals lead to execution

| Service            | Usage                               | Cost              |
| ------------------ | ----------------------------------- | ----------------- |
| Lambda (Analysis)  | 8,640 invocations × 300s × 512MB    | $5.00             |
| Lambda (Approval)  | 4,320 invocations × 30s × 256MB     | $0.50             |
| Lambda (Execution) | 3,456 invocations × 900s × 1GB      | $20.00            |
| DynamoDB           | 8,640 writes, 12,096 reads          | $2.00             |
| S3                 | 12,096 PUT, 3,456 GET, 50GB storage | $3.00             |
| SNS                | 16,416 messages                     | $1.00             |
| EventBridge        | 8,640 events                        | $0.10             |
| API Gateway        | 4,320 requests                      | $0.15             |
| Bedrock Agent      | 12,096 invocations                  | $50.00            |
| **Total**          |                                     | **~$81.75/month** |

---

## Next Steps

1. ✅ Deploy Lambda functions
2. ✅ Create DynamoDB table
3. ✅ Set up S3 bucket
4. ✅ Configure SNS topics
5. ✅ Create API Gateway
6. ✅ Set up EventBridge schedule
7. ✅ Configure Teams/Slack webhooks
8. ✅ Test end-to-end workflow
9. ✅ Set up monitoring and alarms
10. ✅ Document runbook for on-call team

---

## Support

For issues or questions:
- Check CloudWatch Logs for Lambda functions
- Review DynamoDB items for alert status
- Test webhooks manually
- Verify IAM permissions
- Contact AWS support for Bedrock Agent issues

---

*Last updated: 2024*
