# CloudFormation Deployment Guide - Domain Monitor

## Overview

This guide provides instructions for deploying the simplified domain monitoring Lambda function using the updated CloudFormation template (`ping-monitor.yaml`).

## What's Changed

### ✅ Simplified Architecture

**Before (Old Template):**
- Multiple notification channels configured directly
- AI agent credentials in environment variables
- Complex IAM permissions (SNS, Cognito, Bedrock)
- 7+ parameters to configure

**After (New Template):**
- Delegates to invoke handler Lambda
- Minimal environment variables (2)
- Simple IAM permissions (Lambda invoke only)
- 4 core parameters (+ 2 optional deployment params)

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **S3 Bucket** for Lambda deployment package
3. **Invoke Handler Lambda** already deployed (receives events from monitor)
4. **AWS CLI** installed and configured

## Parameters

### Required Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `InvokeLambdaName` | Name/ARN of invoke handler Lambda | `aws-cloudops-invoke-handler` | `my-invoke-handler` |
| `DomainToMonitor` | Domain to monitor | `nghuy.link` | `example.com` |

### Optional Parameters

| Parameter | Description | Default | Options |
|-----------|-------------|---------|---------|
| `MonitoringSchedule` | Monitoring frequency | `rate(5 minutes)` | See [schedule options](#monitoring-schedule-options) |
| `LambdaDeploymentBucket` | S3 bucket for code | (empty) | `my-lambda-bucket` |
| `LambdaDeploymentKey` | S3 key for code | `ping-monitor/lambda_domain_monitor.zip` | `lambdas/monitor.zip` |

### Monitoring Schedule Options

- `rate(1 minute)` - Every minute (high frequency)
- `rate(5 minutes)` - Every 5 minutes (recommended)
- `rate(10 minutes)` - Every 10 minutes
- `rate(15 minutes)` - Every 15 minutes
- `rate(30 minutes)` - Every 30 minutes
- `rate(1 hour)` - Hourly (low frequency)

## Deployment Steps

### Step 1: Prepare Lambda Deployment Package

```bash
cd c:\Workspace\AwsCloudOpsAgent

# Create deployment package directory
mkdir -p build/lambda_domain_monitor

# Copy Lambda function
cp src/lambdas/lambda_domain_monitor.py build/lambda_domain_monitor/

# Install dependencies (minimal - only boto3 needed, but it's included in Lambda runtime)
pip install boto3 -t build/lambda_domain_monitor/

# Create ZIP package
cd build/lambda_domain_monitor
zip -r ../lambda_domain_monitor.zip .
cd ../..
```

### Step 2: Upload to S3

```bash
# Set your bucket name
S3_BUCKET="your-lambda-deployment-bucket"

# Upload the package
aws s3 cp build/lambda_domain_monitor.zip s3://${S3_BUCKET}/ping-monitor/lambda_domain_monitor.zip
```

### Step 3: Deploy CloudFormation Stack

#### Option A: Using AWS Console

1. Navigate to **CloudFormation** in AWS Console
2. Click **Create Stack** → **With new resources**
3. Choose **Upload a template file**
4. Upload `cloudformation/ping-monitor.yaml`
5. Configure parameters:
   - **Stack name**: `domain-monitor-stack`
   - **InvokeLambdaName**: Your invoke handler function name
   - **DomainToMonitor**: Your domain (e.g., `example.com`)
   - **MonitoringSchedule**: Choose frequency
   - **LambdaDeploymentBucket**: Your S3 bucket name
6. Click **Next** → Review → **Create Stack**

#### Option B: Using AWS CLI

```bash
# Set variables
STACK_NAME="domain-monitor-stack"
INVOKE_LAMBDA="aws-cloudops-invoke-handler"
DOMAIN="nghuy.link"
SCHEDULE="rate(5 minutes)"
S3_BUCKET="your-lambda-bucket"

# Deploy stack
aws cloudformation create-stack \
  --stack-name ${STACK_NAME} \
  --template-body file://cloudformation/ping-monitor.yaml \
  --parameters \
    ParameterKey=InvokeLambdaName,ParameterValue=${INVOKE_LAMBDA} \
    ParameterKey=DomainToMonitor,ParameterValue=${DOMAIN} \
    ParameterKey=MonitoringSchedule,ParameterValue="${SCHEDULE}" \
    ParameterKey=LambdaDeploymentBucket,ParameterValue=${S3_BUCKET} \
    ParameterKey=LambdaDeploymentKey,ParameterValue=ping-monitor/lambda_domain_monitor.zip \
  --capabilities CAPABILITY_NAMED_IAM

# Wait for stack creation to complete
aws cloudformation wait stack-create-complete \
  --stack-name ${STACK_NAME}

# Check status
aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --query 'Stacks[0].StackStatus'
```

### Step 4: Verify Deployment

```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --query 'Stacks[0].Outputs' \
  --output table

# Test the Lambda function manually
aws lambda invoke \
  --function-name domain-ping-monitor \
  --payload '{}' \
  response.json

# Check the response
cat response.json
```

## Stack Outputs

After deployment, the stack provides these outputs:

| Output | Description | Usage |
|--------|-------------|-------|
| `FunctionName` | Lambda function name | For manual invocations |
| `FunctionArn` | Lambda function ARN | For IAM policies |
| `ScheduleRule` | EventBridge rule ARN | Monitor schedule |
| `MonitoredDomain` | Domain being monitored | Reference |
| `InvokeLambda` | Target invoke handler | Verify configuration |
| `RoleArn` | IAM role ARN | For troubleshooting |

## Updating the Stack

### Update Lambda Code

```bash
# Update the deployment package
cd c:\Workspace\AwsCloudOpsAgent
# ... make code changes ...

# Rebuild and upload
cd build/lambda_domain_monitor
zip -r ../lambda_domain_monitor.zip .
aws s3 cp ../lambda_domain_monitor.zip s3://${S3_BUCKET}/ping-monitor/lambda_domain_monitor.zip

# Force Lambda to update
aws lambda update-function-code \
  --function-name domain-ping-monitor \
  --s3-bucket ${S3_BUCKET} \
  --s3-key ping-monitor/lambda_domain_monitor.zip
```

### Update Stack Parameters

```bash
aws cloudformation update-stack \
  --stack-name ${STACK_NAME} \
  --use-previous-template \
  --parameters \
    ParameterKey=InvokeLambdaName,UsePreviousValue=true \
    ParameterKey=DomainToMonitor,ParameterValue=new-domain.com \
    ParameterKey=MonitoringSchedule,ParameterValue="rate(10 minutes)" \
    ParameterKey=LambdaDeploymentBucket,UsePreviousValue=true \
    ParameterKey=LambdaDeploymentKey,UsePreviousValue=true \
  --capabilities CAPABILITY_NAMED_IAM
```

## Monitoring & Troubleshooting

### View Lambda Logs

```bash
# Get recent logs
aws logs tail /aws/lambda/domain-ping-monitor --follow

# Query specific time range
aws logs filter-log-events \
  --log-group-name /aws/lambda/domain-ping-monitor \
  --start-time $(date -d '1 hour ago' +%s)000
```

### Check EventBridge Rule

```bash
# Verify rule is enabled
aws events describe-rule --name domain-monitor-schedule

# View rule metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/Events \
  --metric-name Invocations \
  --dimensions Name=RuleName,Value=domain-monitor-schedule \
  --start-time $(date -u -d '1 day ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Sum
```

### Common Issues

#### Issue 1: Lambda not invoking handler

**Symptom:** Monitor detects issues but no analysis happens

**Solution:**
```bash
# Check IAM permissions
aws iam get-role-policy \
  --role-name domain-monitor-role \
  --policy-name InvokeLambdaHandler

# Verify invoke handler exists
aws lambda get-function --function-name ${INVOKE_LAMBDA}

# Test invoke permission manually
aws lambda invoke \
  --function-name ${INVOKE_LAMBDA} \
  --payload '{"test":"true"}' \
  response.json
```

#### Issue 2: Permission denied errors

**Symptom:** CloudWatch logs show "AccessDeniedException"

**Solution:**
```bash
# Update IAM role with correct invoke handler ARN
aws cloudformation update-stack \
  --stack-name ${STACK_NAME} \
  --use-previous-template \
  --parameters \
    ParameterKey=InvokeLambdaName,ParameterValue=correct-function-name \
    # ... other parameters ...
  --capabilities CAPABILITY_NAMED_IAM
```

#### Issue 3: Domain always shows as healthy (testing)

**Solution:**
```python
# Uncomment the test line in lambda_domain_monitor.py line 60:
raise Exception("Simulated unreachable domain for testing purposes")

# Redeploy the code
```

## Cost Estimates

Based on typical usage with `rate(5 minutes)` monitoring:

| Resource | Monthly Invocations | Estimated Cost |
|----------|---------------------|----------------|
| Lambda (Monitor) | ~8,640 | $0.00 (within free tier) |
| CloudWatch Logs | 1 GB | $0.50 |
| EventBridge | 8,640 invocations | $0.01 |
| **Total** | | **~$0.51/month** |

## Security Considerations

### IAM Least Privilege

The new template follows least privilege principle:
- ✅ Only Lambda invoke permission
- ✅ CloudWatch Logs (via managed policy)
- ❌ No SNS, S3, DynamoDB, Bedrock permissions

### Sensitive Data

No sensitive data in environment variables:
- ❌ No passwords or API keys
- ❌ No webhook URLs
- ✅ Only function names and domain

### Network Security

If your invoke handler is in a VPC:
```yaml
# Add to PingMonitorFunction properties:
VpcConfig:
  SecurityGroupIds:
    - !Ref MonitorSecurityGroup
  SubnetIds:
    - !Ref PrivateSubnet1
    - !Ref PrivateSubnet2
```

## Cleanup

### Delete Stack

```bash
# Delete the CloudFormation stack
aws cloudformation delete-stack --stack-name ${STACK_NAME}

# Wait for deletion
aws cloudformation wait stack-delete-complete --stack-name ${STACK_NAME}

# Clean up S3 deployment package
aws s3 rm s3://${S3_BUCKET}/ping-monitor/lambda_domain_monitor.zip
```

## Multi-Region Deployment

To deploy monitors in multiple regions:

```bash
REGIONS=("us-east-1" "eu-west-1" "ap-southeast-1")

for REGION in "${REGIONS[@]}"; do
  echo "Deploying to ${REGION}..."
  aws cloudformation create-stack \
    --stack-name domain-monitor-${REGION} \
    --region ${REGION} \
    --template-body file://cloudformation/ping-monitor.yaml \
    --parameters \
      ParameterKey=InvokeLambdaName,ParameterValue=${INVOKE_LAMBDA} \
      ParameterKey=DomainToMonitor,ParameterValue=${DOMAIN} \
      ParameterKey=MonitoringSchedule,ParameterValue="${SCHEDULE}" \
      ParameterKey=LambdaDeploymentBucket,ParameterValue=${S3_BUCKET}-${REGION} \
    --capabilities CAPABILITY_NAMED_IAM
done
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Deploy Domain Monitor

on:
  push:
    branches: [main]
    paths:
      - 'src/lambdas/lambda_domain_monitor.py'
      - 'cloudformation/ping-monitor.yaml'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ap-southeast-1
      
      - name: Package Lambda
        run: |
          cd src/lambdas
          zip lambda_domain_monitor.zip lambda_domain_monitor.py
          aws s3 cp lambda_domain_monitor.zip s3://${{ secrets.S3_BUCKET }}/ping-monitor/
      
      - name: Deploy CloudFormation
        run: |
          aws cloudformation deploy \
            --stack-name domain-monitor-stack \
            --template-file cloudformation/ping-monitor.yaml \
            --parameter-overrides \
              InvokeLambdaName=${{ secrets.INVOKE_LAMBDA }} \
              DomainToMonitor=${{ secrets.DOMAIN }} \
              LambdaDeploymentBucket=${{ secrets.S3_BUCKET }} \
            --capabilities CAPABILITY_NAMED_IAM
```

## Next Steps

1. **Deploy Invoke Handler**: Ensure `lambda_invoke_handler` is deployed first
2. **Test Workflow**: Trigger a test alert to verify end-to-end flow
3. **Set Up Monitoring**: Configure CloudWatch dashboards
4. **Add More Monitors**: Deploy additional service monitors using the same pattern

## Related Documentation

- [Lambda Domain Monitor Update](./LAMBDA_DOMAIN_MONITOR_UPDATE.md)
- [Architecture Comparison](./ARCHITECTURE_COMPARISON.md)
- [Agent Workflow Best Practices](./AGENT_WORKFLOW_BEST_PRACTICES.md)

---

*Last Updated: December 13, 2025*
