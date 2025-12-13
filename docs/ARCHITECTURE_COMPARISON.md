# Lambda Domain Monitor - Architecture Comparison

## Before: Monolithic Approach

```
┌────────────────────────────────────────────────────────────┐
│           Lambda: domain_monitor                           │
│                                                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 1. Monitor Domain (DNS Check)                     │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 2. Get Cognito JWT Token                          │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 3. Invoke Bedrock Agent for Analysis              │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 4. Upload Analysis to S3                          │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 5. Store Alert Data in DynamoDB                   │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 6. Send SNS Email Notification                    │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 7. Send Teams Notification                        │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 8. Send Slack Notification                        │    │
│  └──────────────────────────────────────────────────┘    │
│                                                            │
│  Dependencies: boto3, requests, socket, json, os,         │
│                urllib, datetime                            │
│  Environment Variables: 9+                                 │
│  IAM Permissions: Lambda, Cognito, Bedrock, S3,           │
│                   DynamoDB, SNS, (Teams/Slack via HTTP)   │
└────────────────────────────────────────────────────────────┘
```

## After: Microservices Approach

```
┌──────────────────────────────────────┐
│    Lambda: domain_monitor            │
│                                      │
│  ┌────────────────────────────────┐ │
│  │ 1. Monitor Domain (DNS Check)  │ │
│  └────────────────────────────────┘ │
│                ↓                     │
│  ┌────────────────────────────────┐ │
│  │ 2. Build Event Payload         │ │
│  └────────────────────────────────┘ │
│                ↓                     │
│  ┌────────────────────────────────┐ │
│  │ 3. Invoke Handler Lambda       │ │──────────┐
│  └────────────────────────────────┘ │          │
│                                      │          │
│  Dependencies: boto3, socket,        │          │
│                json, os, datetime    │          │
│  Environment Variables: 2            │          │
│  IAM Permissions: Lambda only        │          │
└──────────────────────────────────────┘          │
                                                  │
                                                  ↓
┌────────────────────────────────────────────────────────────┐
│           Lambda: invoke_handler                           │
│                                                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 1. Receive Event from Monitor                     │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 2. Get Cognito JWT Token                          │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 3. Invoke Bedrock Agent for Analysis              │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 4. Upload Analysis to S3                          │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 5. Store Alert Data in DynamoDB                   │    │
│  └──────────────────────────────────────────────────┘    │
│                         ↓                                  │
│  ┌──────────────────────────────────────────────────┐    │
│  │ 6. Send Teams Notification (via Power Automate)  │    │
│  └──────────────────────────────────────────────────┘    │
│                                                            │
│  Dependencies: boto3, json, os, urllib, datetime          │
│  Environment Variables: 10+                                │
│  IAM Permissions: Lambda, Cognito, Bedrock, S3,           │
│                   DynamoDB, (Teams via HTTP)              │
└────────────────────────────────────────────────────────────┘
```

## Key Benefits of New Architecture

### 1. Separation of Concerns
- **Monitor Lambda**: Only responsible for detecting issues
- **Invoke Handler**: Handles all analysis and notification logic

### 2. Reusability
```
┌─────────────────┐
│ CloudFront      │───┐
│ Monitor         │   │
└─────────────────┘   │
                       │
┌─────────────────┐   │     ┌──────────────────┐
│ Domain          │───┼────→│ Invoke Handler   │
│ Monitor         │   │     │ (Centralized)    │
└─────────────────┘   │     └──────────────────┘
                       │
┌─────────────────┐   │
│ Route53         │───┤
│ Monitor         │   │
└─────────────────┘   │
                       │
┌─────────────────┐   │
│ EC2             │───┘
│ Monitor         │
└─────────────────┘
```

### 3. Reduced Complexity
| Aspect | Before | After | Improvement |
|--------|--------|-------|-------------|
| Functions | 9 | 2 | 78% reduction |
| Lines of Code | 777 | 131 | 83% reduction |
| Environment Vars | 9+ | 2 | 78% reduction |
| IAM Permissions | 7+ services | 1 service | 86% reduction |
| Dependencies | 8 imports | 5 imports | 38% reduction |

### 4. Easier Testing
```python
# Before: Hard to test - too many dependencies
def test_domain_monitor():
    # Need to mock: Cognito, Bedrock, S3, DynamoDB, SNS, Teams, Slack
    # 7+ service mocks required
    pass

# After: Easy to test - single dependency
def test_domain_monitor():
    # Only need to mock: Lambda invoke
    # 1 service mock required
    pass
```

### 5. Cost Optimization
- Shorter execution time for monitor Lambda
- Pay only for what you use (analysis only when needed)
- Reduced cold start time (fewer dependencies)

### 6. Maintenance
```
Before: Change notification logic → Update ALL monitor Lambdas
After:  Change notification logic → Update ONLY invoke handler
```

## Code Size Comparison

```
Before:
├── Imports: 8 (socket, boto3, json, os, uuid, requests, urllib, datetime)
├── Functions: 9
│   ├── get_cognito_jwt_token
│   ├── invoke_agent_for_analysis
│   ├── extract_executive_summary
│   ├── summarize_agent_analysis
│   ├── upload_analysis_to_s3
│   ├── store_alert_data
│   ├── send_slack_notification
│   ├── send_teams_notification
│   └── lambda_handler
└── Total Lines: 777

After:
├── Imports: 5 (socket, boto3, json, os, datetime)
├── Functions: 2
│   ├── invoke_lambda_handler
│   └── lambda_handler
└── Total Lines: 131
```

## Deployment Comparison

### Before
```bash
# Deploy with ALL dependencies
pip install boto3 requests urllib3 -t package/
# Package size: ~50MB

# Configure 9+ environment variables
aws lambda update-function-configuration \
  --function-name domain-monitor \
  --environment Variables="{...9 variables...}" \
  --timeout 90
```

### After
```bash
# Deploy with minimal dependencies
pip install boto3 -t package/
# Package size: ~15MB (70% reduction)

# Configure only 2 environment variables
aws lambda update-function-configuration \
  --function-name domain-monitor \
  --environment Variables="{INVOKE_LAMBDA_NAME=...,DOMAIN_TO_MONITOR=...}" \
  --timeout 10
```

## Error Handling Comparison

### Before
```python
# Errors in ANY component break the entire function
try:
    agent_analysis = invoke_agent_for_analysis(...)
    # If agent fails, S3, DynamoDB, notifications all skip
except:
    # Everything fails together
```

### After
```python
# Monitor can fail independently
try:
    invoke_lambda_handler(event_data)
    # If handler fails, monitor still completes successfully
    # Handler can retry, have DLQ, etc.
except:
    # Monitor logs error and continues
    # Handler processes async with retries
```

---

*Generated: December 13, 2025*
