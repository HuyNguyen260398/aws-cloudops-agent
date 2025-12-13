# Lambda Domain Monitor - Update Summary

## Overview
Updated `lambda_domain_monitor.py` to simplify its workflow by delegating AI agent analysis to the `lambda_invoke_handler` Lambda function.

## What Changed

### Before (Old Implementation)
The domain monitor Lambda performed:
1. ✅ Domain health check (DNS resolution)
2. ✅ AI agent invocation for analysis
3. ✅ S3 upload of full analysis report
4. ✅ DynamoDB storage for workflow tracking  
5. ✅ SNS email notifications
6. ✅ Microsoft Teams notifications
7. ✅ Slack notifications

**Problems:**
- Duplicated logic between monitor and invoke handler
- Tightly coupled to specific notification channels
- Hard to maintain and extend
- Mixed responsibilities (monitoring + analysis + notification)

### After (New Implementation)
The domain monitor Lambda now only:
1. ✅ Domain health check (DNS resolution)
2. ✅ **Forward issue details to `lambda_invoke_handler`**
3. ❌ ~~AI agent invocation~~ (delegated)
4. ❌ ~~S3 upload~~ (delegated)
5. ❌ ~~DynamoDB storage~~ (delegated)
6. ❌ ~~Direct notifications~~ (delegated)

**Benefits:**
- Single responsibility: monitoring only
- Centralized analysis logic in `lambda_invoke_handler`
- Easier to test and maintain
- Consistent workflow for all service monitors
- Follows AWS best practices for Lambda design

## New Workflow

```
┌───────────────────────────┐
│  Lambda: Domain Monitor   │
│                           │
│  1. Ping domain           │
│  2. Detect issue          │
│  3. Build event payload   │
│  4. Invoke handler Lambda │
└───────────────────────────┘
              ↓
┌───────────────────────────┐
│ Lambda: Invoke Handler    │
│                           │
│  1. Receive event         │
│  2. Invoke AI agent       │
│  3. Upload analysis to S3 │
│  4. Store in DynamoDB     │
│  5. Send notifications    │
└───────────────────────────┘
```

## Event Payload Structure

The domain monitor sends the following event to the invoke handler:

```python
{
    "service_name": "nghuy.link",
    "service_type": "Domain/Website",
    "error_details": "DNS resolution failed: [error details]",
    "issue_type": "domain_unreachable",
    "severity": "critical",
    "status": "DOWN",
    "context": {
        "aws_services": [
            "Amazon Route 53",
            "Amazon CloudFront",
            "AWS Certificate Manager (ACM)",
            "Amazon S3",
            "AWS WAF"
        ],
        "infrastructure_info": "Domain nghuy.link is hosted on AWS using Route 53 for DNS, CloudFront as CDN, S3 for static hosting, and ACM for SSL/TLS certificates.",
        "monitoring_source": "lambda_domain_monitor",
        "detection_method": "DNS resolution check"
    },
    "metadata": {
        "domain": "nghuy.link",
        "timestamp": "2025-12-13T10:30:00",
        "lambda_function": "domain-monitor",
        "request_id": "abc-123-def-456"
    }
}
```

## Required Environment Variables

The domain monitor now only needs:

| Variable | Description | Example |
|----------|-------------|---------|
| `INVOKE_LAMBDA_NAME` | Name/ARN of the invoke handler Lambda | `aws-cloudops-invoke-handler` |
| `DOMAIN_TO_MONITOR` | Domain to monitor (optional) | `nghuy.link` |

### Removed Variables (No Longer Needed)
- ❌ `AGENT_RUNTIME_ARN` - Moved to invoke handler
- ❌ `COGNITO_USERNAME` - Moved to invoke handler
- ❌ `COGNITO_PASSWORD` - Moved to invoke handler
- ❌ `COGNITO_CLIENT_ID` - Moved to invoke handler
- ❌ `S3_ANALYSIS_BUCKET` - Moved to invoke handler
- ❌ `DYNAMODB_ALERTS_TABLE` - Moved to invoke handler
- ❌ `SNS_TOPIC_ARN` - Moved to invoke handler
- ❌ `TEAMS_WEBHOOK_URL` - Moved to invoke handler
- ❌ `SLACK_WEBHOOK_URL` - Moved to invoke handler

## IAM Permissions

The domain monitor Lambda now requires minimal permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "lambda:InvokeFunction"
      ],
      "Resource": "arn:aws:lambda:region:account:function:aws-cloudops-invoke-handler"
    }
  ]
}
```

## Code Size Reduction

| Metric | Before | After | Reduction |
|--------|--------|-------|-----------|
| Lines of Code | ~777 | ~131 | **83%** |
| Functions | 9 | 2 | **78%** |
| Dependencies | 8 imports | 5 imports | **38%** |
| Responsibilities | 7 | 2 | **71%** |

## Testing

To test the new implementation:

1. **Simulate domain failure:**
   ```python
   # In lambda_domain_monitor.py, uncomment line 60:
   raise Exception("Simulated unreachable domain for testing purposes")
   ```

2. **Set environment variables:**
   ```bash
   export INVOKE_LAMBDA_NAME="aws-cloudops-invoke-handler"
   export DOMAIN_TO_MONITOR="nghuy.link"
   ```

3. **Invoke locally:**
   ```bash
   # Test event
   aws lambda invoke \
     --function-name domain-monitor \
     --payload '{}' \
     response.json
   ```

4. **Verify:**
   - Check CloudWatch logs for domain monitor
   - Confirm invoke handler was triggered
   - Verify event payload structure

## Migration Steps

If you have an existing deployment:

1. **Update environment variables:**
   ```bash
   aws lambda update-function-configuration \
     --function-name domain-monitor \
     --environment Variables="{INVOKE_LAMBDA_NAME=aws-cloudops-invoke-handler,DOMAIN_TO_MONITOR=nghuy.link}"
   ```

2. **Update IAM role:**
   - Remove permissions for Bedrock, S3, DynamoDB, SNS, etc.
   - Add permission to invoke the handler Lambda

3. **Deploy updated code:**
   ```bash
   cd c:\Workspace\AwsCloudOpsAgent
   # Package and deploy using your preferred method
   ```

4. **Test the workflow:**
   - Trigger a test alert
   - Verify the full workflow completes
   - Check all notifications are sent

## Related Files

- [lambda_domain_monitor.py](../src/lambdas/lambda_domain_monitor.py) - Updated monitor
- [lambda_invoke_handler.py](../src/lambdas/lambda_invoke_handler.py) - Receives events
- [AGENT_WORKFLOW_BEST_PRACTICES.md](./AGENT_WORKFLOW_BEST_PRACTICES.md) - Full workflow documentation

## Next Steps

1. Update CloudFormation/Terraform templates with new environment variables
2. Create additional service monitors following the same pattern:
   - `lambda_cloudfront_monitor.py`
   - `lambda_route53_monitor.py`
   - `lambda_s3_monitor.py`
3. Implement centralized error handling in invoke handler
4. Add retry logic with exponential backoff

---

*Last Updated: December 13, 2025*
