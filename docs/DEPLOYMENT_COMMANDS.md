# Lambda Ping Monitor - Deployment Commands Reference

Complete reference guide with all commands used throughout development and deployment.

## Table of Contents

- [Deployment](#deployment)
- [Manual Update Commands](#manual-update-commands)
- [Monitoring & Testing](#monitoring--testing)
- [Formatting Agent Response](#formatting-agent-response)
- [Troubleshooting](#troubleshooting)
- [Local Testing](#local-testing)
- [Complete Status Check](#complete-deployment-status-check)
- [Configuration Reference](#configuration-files)

## Deployment

### Full Deployment (with packaging)

```powershell
.\deploy-ping-monitor.ps1

```

### Skip Packaging (use existing zip)

```powershell
.\deploy-ping-monitor.ps1 -SkipPackage

```

### With Custom Parameters

```powershell
.\deploy-ping-monitor.ps1 `
    -Region "ap-southeast-1" `
    -SlackWebhookUrl "" `
    -TeamsWebhookUrl "https://outlook.office.com/webhook/..." `
    -AgentRuntimeArn "arn:aws:bedrock-agentcore:region:account:runtime/name"

```

## Manual Update Commands

### Update Lambda Function Code Only

```powershell
# Package the function
$packageDir = "package"
$zipFile = "lambda_ping_monitor.zip"
Remove-Item -Recurse -Force $packageDir -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $packageDir | Out-Null
pip install --target $packageDir requests boto3 -q
Copy-Item "src\lambda_ping_monitor.py" -Destination $packageDir
Push-Location $packageDir
Compress-Archive -Path * -DestinationPath "..\$zipFile" -CompressionLevel Optimal -Force
Pop-Location
Remove-Item -Recurse -Force $packageDir

# Upload to S3
aws s3 cp lambda_ping_monitor.zip s3://lambda-deployments-ap-southeast-1/ping-monitor/lambda_ping_monitor.zip --region ap-southeast-1

# Update Lambda function
aws lambda update-function-code `
    --function-name domain-ping-monitor `
    --s3-bucket lambda-deployments-ap-southeast-1 `
    --s3-key ping-monitor/lambda_ping_monitor.zip `
    --region ap-southeast-1 `
    --query '[FunctionName,LastModified,CodeSize,State]' `
    --output table

```

### Update Environment Variables Only

```powershell
aws lambda update-function-configuration `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --environment '{
        "Variables": {
            "SNS_TOPIC_ARN": "",
            "TEAMS_WEBHOOK_URL": "",
            "SLACK_WEBHOOK_URL": "",
            "AGENT_RUNTIME_ARN": "",
            "COGNITO_USERNAME": "",
            "COGNITO_PASSWORD": "",
            "COGNITO_CLIENT_ID": ""
        }
    }' `
    --query '[FunctionName,LastModified,State]' `
    --output table

```

## Monitoring & Testing

### Check Stack Status

```powershell
aws cloudformation describe-stacks `
    --stack-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query 'Stacks[0].[StackName,StackStatus,StackStatusReason]' `
    --output table

```

### View Stack Outputs

```powershell
aws cloudformation describe-stacks `
    --stack-name domain-ping-monitor `
    --query 'Stacks[0].Outputs' `
    --output table `
    --region ap-southeast-1

```

### Check Lambda Function Configuration

```powershell
aws lambda get-function-configuration `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query '{FunctionName:FunctionName,Runtime:Runtime,Timeout:Timeout,Memory:MemorySize,LastModified:LastModified,State:State}' `
    --output table

```

### View Environment Variables

```powershell
aws lambda get-function-configuration `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query 'Environment.Variables' `
    --output json | ConvertFrom-Json | Format-List

```

### Test Lambda Function

```powershell
# Invoke and see logs
aws lambda invoke `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --log-type Tail `
    --query 'LogResult' `
    --output text output.json | ForEach-Object { 
        [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) 
    }

# View response
Get-Content output.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

```

### Comprehensive Test with Output

```powershell
Write-Host "``n=====================================" -ForegroundColor Cyan
Write-Host "Testing Lambda Function" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

aws lambda invoke `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --log-type Tail `
    --query 'LogResult' `
    --output text output.json | ForEach-Object { 
        [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) 
    }

Write-Host "``nFunction Response:" -ForegroundColor Cyan
Get-Content output.json | ConvertFrom-Json | ConvertTo-Json -Depth 10

```

### View CloudWatch Logs

```powershell
# Get latest log stream
aws logs describe-log-streams `
    --log-group-name /aws/lambda/domain-ping-monitor `
    --region ap-southeast-1 `
    --order-by LastEventTime `
    --descending `
    --max-items 1 `
    --query 'logStreams[0].logStreamName' `
    --output text

# View recent logs (tail and follow)
aws logs tail /aws/lambda/domain-ping-monitor `
    --region ap-southeast-1 `
    --follow

```

## Formatting Agent Response

### Pretty Print Agent Response File

```powershell
Get-Content .\agent_response.txt -Raw | ForEach-Object { 
    $_ -replace '\\n', "``n" `
       -replace '\\ud83d\\udea8', '' `
       -replace '\\ud83d\\udccb', '' `
       -replace '\\ud83d\\udd0d', '' `
       -replace '\\u2705', '' `
       -replace '\\u26a0\\ufe0f', '' `
       -replace '\\u274c', '' `
       -replace '\\ud83d\\udcca', '' `
       -replace '\\ud83d\\udd34', '' `
       -replace '\\ud83d\\udd27', '' `
       -replace '\\u2192', ''
} | Write-Host

```

## Troubleshooting

### View CloudFormation Stack Events

```powershell
aws cloudformation describe-stack-events `
    --stack-name domain-ping-monitor `
    --region ap-southeast-1 `
    --max-items 10 `
    --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,ResourceStatusReason]' `
    --output table

```

### Check for Failed Updates

```powershell
aws cloudformation describe-stack-events `
    --stack-name domain-ping-monitor `
    --region ap-southeast-1 `
    --max-items 10 `
    --output json | ConvertFrom-Json | 
    Select-Object -ExpandProperty StackEvents | 
    Where-Object { $_.ResourceStatusReason -like '*fail*' -or $_.ResourceStatusReason -like '*error*' } | 
    Select-Object Timestamp, ResourceType, ResourceStatus, ResourceStatusReason | 
    Format-List

```

### Validate CloudFormation Template

```powershell
aws cloudformation validate-template `
    --template-body file://cloudformation/ping-monitor.yaml `
    --region ap-southeast-1

```

### Create and Execute Change Set Manually

```powershell
# Create change set with timestamp
$changeSetName = "manual-update-$(Get-Date -Format 'yyyyMMddHHmmss')"

aws cloudformation create-change-set `
    --stack-name domain-ping-monitor `
    --change-set-name $changeSetName `
    --template-body file://cloudformation/ping-monitor.yaml `
    --capabilities CAPABILITY_IAM `
    --parameters ParameterKey=LambdaDeploymentBucket,ParameterValue=lambda-deployments-ap-southeast-1 `
                 ParameterKey=LambdaDeploymentKey,ParameterValue=ping-monitor/lambda_ping_monitor.zip `
                 ParameterKey=CognitoUsername,ParameterValue=ted8hc `
                 ParameterKey=CognitoPassword,ParameterValue= `
                 ParameterKey=CognitoClientId,ParameterValue=40ede8sr0l0bs37hps0lbgvr8p `
                 ParameterKey=SlackWebhookUrl,ParameterValue=https://hooks.slack.com/services/... `
                 ParameterKey=AgentRuntimeArn,ParameterValue=arn:aws:bedrock-agentcore:... `
    --region ap-southeast-1

# Wait and check status
Start-Sleep -Seconds 10
aws cloudformation describe-change-set `
    --stack-name domain-ping-monitor `
    --change-set-name $changeSetName `
    --region ap-southeast-1 `
    --query '[Status,StatusReason,Changes[0:3]]' `
    --output json

# Execute change set
aws cloudformation execute-change-set `
    --stack-name domain-ping-monitor `
    --change-set-name $changeSetName `
    --region ap-southeast-1

# Monitor update progress
Start-Sleep -Seconds 30
aws cloudformation describe-stacks `
    --stack-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query 'Stacks[0].[StackName,StackStatus,StackStatusReason]' `
    --output table

```

### Direct Lambda Update (When CloudFormation Fails)

```powershell
# Update Lambda code from S3
aws lambda update-function-code `
    --function-name domain-ping-monitor `
    --s3-bucket lambda-deployments-ap-southeast-1 `
    --s3-key ping-monitor/lambda_ping_monitor.zip `
    --region ap-southeast-1 `
    --query '[FunctionName,LastModified,CodeSize,State]' `
    --output table

# Update environment variables
aws lambda update-function-configuration `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --environment '{
        "Variables": {
            "SNS_TOPIC_ARN": "",
            "TEAMS_WEBHOOK_URL": "",
            "SLACK_WEBHOOK_URL": "",
            "AGENT_RUNTIME_ARN": "",
            "COGNITO_USERNAME": "",
            "COGNITO_PASSWORD": "",
            "COGNITO_CLIENT_ID": ""
        }
    }' `
    --query '[FunctionName,LastModified,State]' `
    --output table

# Verify updates
Write-Host "``nUpdated Environment Variables:" -ForegroundColor Green
aws lambda get-function-configuration `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query 'Environment.Variables' `
    --output json | ConvertFrom-Json | Format-List

```

## Local Testing

### Python Script (Simple)

```powershell
# Basic test (without SNS)
python test_lambda_local.py --skip-sns

# With Slack webhook
python test_lambda_local.py --skip-sns --slack-webhook "https://hooks.slack.com/..."

# Full test with agent
python test_lambda_local.py --skip-sns --agent-arn "arn:aws:bedrock-agentcore:..." --slack-webhook "https://hooks.slack.com/..."

```

### AWS SAM CLI

```powershell
# Install SAM CLI first: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

.\test_lambda_docker.ps1 -Method sam -SkipSNS

```

### Docker

```powershell
# Requires Docker Desktop
.\test_lambda_docker.ps1 -Method docker -SkipSNS

```

## Complete Deployment Status Check

```powershell
# Check stack status
Write-Host "``nStack Status:" -ForegroundColor Cyan
aws cloudformation describe-stacks `
    --stack-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query 'Stacks[0].[StackName,StackStatus,StackStatusReason]' `
    --output table

# View stack outputs
Write-Host "``nStack Outputs:" -ForegroundColor Cyan
aws cloudformation describe-stacks `
    --stack-name domain-ping-monitor `
    --query 'Stacks[0].Outputs' `
    --output table `
    --region ap-southeast-1

# Lambda function configuration
Write-Host "``nLambda Function Configuration:" -ForegroundColor Cyan
aws lambda get-function-configuration `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query '{FunctionName:FunctionName,Runtime:Runtime,Timeout:Timeout,Memory:MemorySize,LastModified:LastModified,State:State}' `
    --output table

# Environment variables
Write-Host "``nEnvironment Variables:" -ForegroundColor Cyan
aws lambda get-function-configuration `
    --function-name domain-ping-monitor `
    --region ap-southeast-1 `
    --query 'Environment.Variables' `
    --output json | ConvertFrom-Json | Format-List

```

## Deployment Summary Command

```powershell
Write-Host "``n=====================================" -ForegroundColor Green
Write-Host "Deployment Summary" -ForegroundColor Green
Write-Host "=====================================" -ForegroundColor Green
Write-Host "``nFunction Status: ACTIVE" -ForegroundColor White
Write-Host "Code Updated: $(Get-Date)" -ForegroundColor White
Write-Host "``nConfiguration:" -ForegroundColor Cyan
Write-Host "  Domain: nghuy.link" -ForegroundColor White
Write-Host "  Schedule: Every 5 minutes" -ForegroundColor White
Write-Host "  Timeout: 90 seconds" -ForegroundColor White
Write-Host "  Memory: 256 MB" -ForegroundColor White
Write-Host "``nNotification Channels:" -ForegroundColor Cyan
Write-Host "  Email (SNS): ENABLED" -ForegroundColor Green
Write-Host "  Slack: ENABLED" -ForegroundColor Green
Write-Host "  Teams: DISABLED" -ForegroundColor Yellow
Write-Host "  AI Agent Analysis: ENABLED" -ForegroundColor Green
Write-Host "``nLast Test Result:" -ForegroundColor Cyan
Write-Host "  Status: Domain is healthy (200)" -ForegroundColor Green
Write-Host "  Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
Write-Host ""

```

## Quick Command Reference

```powershell
# Full redeploy
.\deploy-ping-monitor.ps1

# Update code only (quick)
aws lambda update-function-code --function-name domain-ping-monitor --s3-bucket lambda-deployments-ap-southeast-1 --s3-key ping-monitor/lambda_ping_monitor.zip --region ap-southeast-1

# Test function
aws lambda invoke --function-name domain-ping-monitor --region ap-southeast-1 output.json

# View logs (real-time)
aws logs tail /aws/lambda/domain-ping-monitor --region ap-southeast-1 --follow

# Check status
aws cloudformation describe-stacks --stack-name domain-ping-monitor --region ap-southeast-1 --query 'Stacks[0].StackStatus'

# View environment variables
aws lambda get-function-configuration --function-name domain-ping-monitor --region ap-southeast-1 --query 'Environment.Variables' | ConvertFrom-Json | Format-List

```

## Configuration Files

### Environment Variables Reference

- SNS_TOPIC_ARN: ARN of SNS topic for email alerts
- TEAMS_WEBHOOK_URL: Microsoft Teams incoming webhook URL (optional)
- SLACK_WEBHOOK_URL: Slack incoming webhook URL (optional)
- AGENT_RUNTIME_ARN: AWS Bedrock Agent Runtime ARN for AI analysis
- COGNITO_USERNAME: Cognito username for agent authentication
- COGNITO_PASSWORD: Cognito password for agent authentication
- COGNITO_CLIENT_ID: Cognito client ID for agent authentication
- AWS_REGION: Automatically provided by Lambda (cannot be set manually)

### Required IAM Permissions

The Lambda function needs:

- sns:Publish - Send email notifications
- cognito-idp:InitiateAuth - Authenticate with Cognito
- cognito-idp:GetUser - Get user information
- bedrock:InvokeAgent - Invoke Bedrock agent
- bedrock-agentcore:InvokeRuntime - Invoke agent runtime

### CloudFormation Parameters

- LambdaDeploymentBucket: S3 bucket for deployment package
- LambdaDeploymentKey: S3 key for deployment package
- TeamsWebhookUrl: Teams webhook URL
- SlackWebhookUrl: Slack webhook URL
- AgentRuntimeArn: Agent runtime ARN
- CognitoUsername: Cognito username
- CognitoPassword: Cognito password
- CognitoClientId: Cognito client ID

## Common Issues and Solutions

### Issue: AWS_REGION Reserved Variable Error

__Problem:__ CloudFormation fails with "Reserved keys used in this request: AWS_REGION"
__Solution:__ Remove AWS_REGION from environment variables - Lambda provides it automatically

### Issue: CloudFormation Deploy Fails with PropertyValidation

**Problem:** cloudformation deploy fails with validation errors
**Solution:** Use manual changeset approach or update Lambda directly

### Issue: Agent Analysis Returns Escaped Characters

**Problem:** Agent response contains \n and \ud83d\udea8 instead of newlines and emojis
**Solution:** Use the formatting code in the Lambda function (already implemented) or use the pretty print command above

## Notes

- The function runs every 5 minutes via EventBridge schedule
- Timeout is set to 90 seconds to allow for agent analysis
- Agent analysis is formatted with emojis for better readability
- Slack and Teams notifications are truncated to 2800 characters
- Empty webhook URLs are handled gracefully (skipped)
- SNS topic ARN is retrieved from environment variable

## Related Documentation

- [LAMBDA_PING_MONITOR.md](LAMBDA_PING_MONITOR.md) - Detailed function documentation
- [COGNITO_AUTH_SETUP.md](COGNITO_AUTH_SETUP.md) - Cognito setup guide
- [JWT_INVOKE_ANALYSIS.md](JWT_INVOKE_ANALYSIS.md) - JWT authentication details
- [ROADMAP.md](ROADMAP.md) - Project roadmap and future enhancements
