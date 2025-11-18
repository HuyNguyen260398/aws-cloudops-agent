# Lambda Ping Monitor with Teams Integration

## Overview
AWS Lambda function that monitors domain availability and sends alerts through multiple channels when the domain becomes unreachable.

## Features
- **DNS Resolution Check**: Tests domain connectivity using socket DNS lookup
- **Multi-Channel Alerts**:
  - AWS SNS (Email notifications)
  - Microsoft Teams (via Incoming Webhook)
- **Error Handling**: Graceful fallback if notification channels fail

## Function Details

### Target Domain
- **Monitored Domain**: `nghuy.link`

### Notification Channels

#### 1. AWS SNS Email Alerts
- **Topic ARN**: `arn:aws:sns:us-east-1:ACCOUNT_ID:domain-alerts`
- **Subject**: `Domain Alert: {domain} Down`
- **Message**: Includes domain name and timestamp

#### 2. Microsoft Teams Notifications
- **Method**: Incoming Webhook
- **Message Format**: Adaptive Message Card
- **Color Coding**:
  - 🔴 Red (`FF0000`): Domain down
  - 🟢 Green (`00FF00`): Domain up
- **Information Included**:
  - Domain name
  - Status (UP/DOWN)
  - Timestamp

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TEAMS_WEBHOOK_URL` | Yes | Microsoft Teams Incoming Webhook URL |

## Setup Instructions

### 1. Configure Microsoft Teams Webhook
1. Open your Teams channel
2. Go to **Channel Settings** → **Connectors**
3. Add **Incoming Webhook**
4. Copy the webhook URL
5. Add to Lambda environment variables as `TEAMS_WEBHOOK_URL`

### 2. Configure AWS SNS
1. Create SNS topic: `domain-alerts`
2. Subscribe email addresses to the topic
3. Update the ARN in the code with your AWS account ID

### 3. Lambda Configuration
- **Runtime**: Python 3.x
- **Permissions Required**:
  - `sns:Publish` (for SNS notifications)
  - Outbound internet access (for Teams webhook)

## Return Values

| Status Code | Condition | Body |
|-------------|-----------|------|
| 200 | Domain is reachable | `{domain} is healthy` |
| 500 | Domain is unreachable | `ALERT: {domain} is unreachable at {timestamp}` |

## Dependencies
- `boto3` (AWS SDK)
- `socket` (built-in)
- `json` (built-in)
- `urllib` (built-in)

No additional packages required beyond standard AWS Lambda Python runtime.

## Error Handling
- SNS failures are logged but don't prevent Teams notifications
- Teams failures are logged but don't affect function execution
- Missing webhook URL is detected and logged

## Example Teams Message Card Structure

```json
{
  "@type": "MessageCard",
  "@context": "https://schema.org/extensions",
  "themeColor": "FF0000",
  "summary": "Domain Alert: nghuy.link",
  "sections": [{
    "activityTitle": "🚨 Domain Alert: nghuy.link",
    "activitySubtitle": "2025-11-18 10:30:45.123456",
    "facts": [
      {"name": "Domain:", "value": "nghuy.link"},
      {"name": "Status:", "value": "DOWN"},
      {"name": "Timestamp:", "value": "2025-11-18 10:30:45.123456"}
    ],
    "markdown": true
  }]
}
```

## Deployment
Use the provided CloudFormation template or deployment script:
```powershell
.\deploy-ping-monitor.ps1
```

## Testing
Invoke the Lambda function manually to test:
```bash
aws lambda invoke --function-name ping-monitor output.json
```

## Monitoring
- CloudWatch Logs capture all print statements
- Failed notifications are logged with error details
- Monitor Lambda execution metrics in CloudWatch