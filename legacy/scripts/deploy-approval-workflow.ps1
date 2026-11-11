# Deploy Domain Monitor with Slack Approval Workflow
# This script deploys the enhanced monitoring system with interactive Slack cards

param(
    [Parameter(Mandatory=$true)]
    [string]$StackName = "domain-monitor-approval",
    
    [Parameter(Mandatory=$true)]
    [string]$SlackWebhookURL,
    
    [Parameter(Mandatory=$true)]
    [string]$SlackSigningSecret,
    
    [Parameter(Mandatory=$true)]
    [string]$EmailAddress,
    
    [string]$DomainName = "nghuy.link",
    [string]$TeamsWebhookURL = "",
    [string]$CloudFrontDistributionId = "",
    [string]$AgentRuntimeArn = "",
    [string]$CognitoUsername = "",
    [string]$CognitoPassword = "",
    [string]$CognitoClientId = "",
    [string]$MonitoringSchedule = "rate(5 minutes)",
    [string]$Region = "ap-southeast-1"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Domain Monitor with Slack Approval" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Set AWS region
$env:AWS_DEFAULT_REGION = $Region

# Check if stack exists
Write-Host "Checking if stack exists..." -ForegroundColor Yellow
$stackExists = $false
try {
    $stack = aws cloudformation describe-stacks --stack-name $StackName 2>$null | ConvertFrom-Json
    if ($stack.Stacks.Count -gt 0) {
        $stackExists = $true
        Write-Host "Stack exists. Will update." -ForegroundColor Green
    }
} catch {
    Write-Host "Stack does not exist. Will create." -ForegroundColor Green
}

# Prepare parameters
$parameters = @(
    "ParameterKey=DomainName,ParameterValue=$DomainName",
    "ParameterKey=SNSEmailAddress,ParameterValue=$EmailAddress",
    "ParameterKey=SlackWebhookURL,ParameterValue=$SlackWebhookURL",
    "ParameterKey=SlackSigningSecret,ParameterValue=$SlackSigningSecret",
    "ParameterKey=MonitoringSchedule,ParameterValue=$MonitoringSchedule"
)

if ($TeamsWebhookURL) {
    $parameters += "ParameterKey=TeamsWebhookURL,ParameterValue=$TeamsWebhookURL"
}
if ($CloudFrontDistributionId) {
    $parameters += "ParameterKey=CloudFrontDistributionId,ParameterValue=$CloudFrontDistributionId"
}
if ($AgentRuntimeArn) {
    $parameters += "ParameterKey=AgentRuntimeArn,ParameterValue=$AgentRuntimeArn"
}
if ($CognitoUsername) {
    $parameters += "ParameterKey=CognitoUsername,ParameterValue=$CognitoUsername"
}
if ($CognitoPassword) {
    $parameters += "ParameterKey=CognitoPassword,ParameterValue=$CognitoPassword"
}
if ($CognitoClientId) {
    $parameters += "ParameterKey=CognitoClientId,ParameterValue=$CognitoClientId"
}

# Deploy CloudFormation stack
Write-Host ""
Write-Host "Deploying CloudFormation stack..." -ForegroundColor Yellow
Write-Host "Stack Name: $StackName" -ForegroundColor White
Write-Host "Region: $Region" -ForegroundColor White
Write-Host "Domain: $DomainName" -ForegroundColor White
Write-Host ""

if ($stackExists) {
    aws cloudformation update-stack `
        --stack-name $StackName `
        --template-body file://cloudformation/ping-monitor-with-approval.yaml `
        --parameters $parameters `
        --capabilities CAPABILITY_NAMED_IAM
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Waiting for stack update to complete..." -ForegroundColor Yellow
        aws cloudformation wait stack-update-complete --stack-name $StackName
    } else {
        Write-Host "Stack update failed or no changes detected" -ForegroundColor Red
    }
} else {
    aws cloudformation create-stack `
        --stack-name $StackName `
        --template-body file://cloudformation/ping-monitor-with-approval.yaml `
        --parameters $parameters `
        --capabilities CAPABILITY_NAMED_IAM
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Waiting for stack creation to complete..." -ForegroundColor Yellow
        aws cloudformation wait stack-create-complete --stack-name $StackName
    } else {
        Write-Host "Stack creation failed" -ForegroundColor Red
        exit 1
    }
}

# Get stack outputs
Write-Host ""
Write-Host "Retrieving stack outputs..." -ForegroundColor Yellow
$outputs = aws cloudformation describe-stacks --stack-name $StackName --query "Stacks[0].Outputs" | ConvertFrom-Json

$apiEndpoint = ($outputs | Where-Object { $_.OutputKey -eq "ApprovalApiEndpoint" }).OutputValue
$pingMonitorArn = ($outputs | Where-Object { $_.OutputKey -eq "PingMonitorFunctionArn" }).OutputValue
$approvalHandlerArn = ($outputs | Where-Object { $_.OutputKey -eq "ApprovalHandlerFunctionArn" }).OutputValue
$alertsTable = ($outputs | Where-Object { $_.OutputKey -eq "AlertsTableName" }).OutputValue

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Stack deployed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "API Endpoint for Slack: $apiEndpoint" -ForegroundColor Cyan
Write-Host "Ping Monitor Function: $pingMonitorArn" -ForegroundColor White
Write-Host "Approval Handler: $approvalHandlerArn" -ForegroundColor White
Write-Host "Alerts Table: $alertsTable" -ForegroundColor White
Write-Host ""

# Package Lambda functions
Write-Host "Packaging Lambda functions..." -ForegroundColor Yellow

Push-Location src/ops

# Package ping monitor
Write-Host "  - Packaging ping monitor..." -ForegroundColor White
if (Test-Path lambda_ping_monitor.zip) {
    Remove-Item lambda_ping_monitor.zip
}
Compress-Archive -Path lambda_ping_monitor.py -DestinationPath lambda_ping_monitor.zip -Force

# Package approval handler
Write-Host "  - Packaging approval handler..." -ForegroundColor White
if (Test-Path lambda_approval_handler.zip) {
    Remove-Item lambda_approval_handler.zip
}
Compress-Archive -Path lambda_approval_handler.py -DestinationPath lambda_approval_handler.zip -Force

# Deploy Lambda functions
Write-Host ""
Write-Host "Deploying Lambda functions..." -ForegroundColor Yellow

Write-Host "  - Deploying ping monitor..." -ForegroundColor White
aws lambda update-function-code `
    --function-name "$StackName-ping-monitor" `
    --zip-file fileb://lambda_ping_monitor.zip `
    --region $Region | Out-Null

Write-Host "  - Deploying approval handler..." -ForegroundColor White
aws lambda update-function-code `
    --function-name "$StackName-approval-handler" `
    --zip-file fileb://lambda_approval_handler.zip `
    --region $Region | Out-Null

# Clean up
Remove-Item lambda_ping_monitor.zip, lambda_approval_handler.zip -ErrorAction SilentlyContinue

Pop-Location

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "1. Configure Slack App Interactivity:" -ForegroundColor White
Write-Host "   - Go to https://api.slack.com/apps" -ForegroundColor Gray
Write-Host "   - Select your app" -ForegroundColor Gray
Write-Host "   - Navigate to 'Interactivity & Shortcuts'" -ForegroundColor Gray
Write-Host "   - Enable Interactivity" -ForegroundColor Gray
Write-Host "   - Set Request URL to: $apiEndpoint" -ForegroundColor Yellow
Write-Host "   - Save Changes" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Confirm SNS Email Subscription:" -ForegroundColor White
Write-Host "   - Check your email ($EmailAddress)" -ForegroundColor Gray
Write-Host "   - Click the confirmation link" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Test the monitoring:" -ForegroundColor White
Write-Host "   aws lambda invoke --function-name $StackName-ping-monitor response.json" -ForegroundColor Gray
Write-Host ""
Write-Host "For detailed documentation, see:" -ForegroundColor Cyan
Write-Host "   docs/SLACK_APPROVAL_WORKFLOW.md" -ForegroundColor White
Write-Host ""
