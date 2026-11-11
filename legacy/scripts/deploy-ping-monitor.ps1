#!/usr/bin/env pwsh

param(
    [string]$Region = "ap-southeast-1",
    [string]$TeamsWebhookUrl = "",
    [string]$SlackWebhookUrl = "",
    [string]$AgentRuntimeArn = "",
    [string]$CognitoUsername = "",
    [string]$CognitoPassword = "",
    [string]$CognitoClientId = "",
    [string]$S3Bucket = "",
    [switch]$SkipPackage
)

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Domain Ping Monitor Deployment" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Package Lambda function
if (-not $SkipPackage) {
    Write-Host "[1/3] Packaging Lambda function..." -ForegroundColor Yellow
    
    $packageDir = "package"
    $zipFile = "lambda_ping_monitor.zip"
    
    # Create package directory
    if (Test-Path $packageDir) {
        Remove-Item -Recurse -Force $packageDir
    }
    New-Item -ItemType Directory -Path $packageDir | Out-Null
    
    # Install dependencies
    Write-Host "  Installing dependencies..." -ForegroundColor Gray
    pip install --target $packageDir requests boto3 -q
    
    # Copy lambda function
    Write-Host "  Copying lambda function..." -ForegroundColor Gray
    Copy-Item "src\lambda_ping_monitor.py" -Destination $packageDir
    
    # Create zip file
    Write-Host "  Creating deployment package..." -ForegroundColor Gray
    if (Test-Path $zipFile) {
        Remove-Item -Force $zipFile
    }
    
    Push-Location $packageDir
    Compress-Archive -Path * -DestinationPath "..\$zipFile" -CompressionLevel Optimal
    Pop-Location
    
    # Cleanup
    Remove-Item -Recurse -Force $packageDir
    
    Write-Host "  Package created: $zipFile" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[1/3] Skipping package step (using existing package)" -ForegroundColor Yellow
    Write-Host ""
}

# Step 2: Upload to S3
Write-Host "[2/3] Uploading to S3..." -ForegroundColor Yellow

if (-not $S3Bucket) {
    $S3Bucket = "lambda-deployments-$Region"
}

$s3Key = "ping-monitor/lambda_ping_monitor.zip"

# Check if bucket exists, create if needed
$bucketExists = aws s3 ls "s3://$S3Bucket" 2>$null
if (-not $bucketExists) {
    Write-Host "  Creating S3 bucket: $S3Bucket" -ForegroundColor Gray
    aws s3 mb "s3://$S3Bucket" --region $Region
}

Write-Host "  Uploading to s3://$S3Bucket/$s3Key" -ForegroundColor Gray
aws s3 cp lambda_ping_monitor.zip "s3://$S3Bucket/$s3Key" --region $Region

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Failed to upload to S3!" -ForegroundColor Red
    exit 1
}

Write-Host "  Upload successful!" -ForegroundColor Green
Write-Host ""

# Step 3: Deploy CloudFormation stack
Write-Host "[3/3] Deploying CloudFormation stack..." -ForegroundColor Yellow

$parameters = @(
    "LambdaDeploymentBucket=$S3Bucket",
    "LambdaDeploymentKey=$s3Key",
    "CognitoUsername=$CognitoUsername",
    "CognitoPassword=$CognitoPassword",
    "CognitoClientId=$CognitoClientId"
)

if ($TeamsWebhookUrl) {
    $parameters += "TeamsWebhookUrl=$TeamsWebhookUrl"
}

if ($SlackWebhookUrl) {
    $parameters += "SlackWebhookUrl=$SlackWebhookUrl"
}

if ($AgentRuntimeArn) {
    $parameters += "AgentRuntimeArn=$AgentRuntimeArn"
}

$parameterOverrides = ($parameters -join " ")

Write-Host "  Deploying stack: domain-ping-monitor" -ForegroundColor Gray
aws cloudformation deploy `
    --template-file cloudformation/ping-monitor.yaml `
    --stack-name domain-ping-monitor `
    --capabilities CAPABILITY_IAM `
    --parameter-overrides $parameterOverrides `
    --region $Region

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host "Deployment Successful!" -ForegroundColor Green
    Write-Host "=====================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Monitor Configuration:" -ForegroundColor Cyan
    Write-Host "  Domain: nghuy.link" -ForegroundColor White
    Write-Host "  Check Interval: Every 5 minutes" -ForegroundColor White
    Write-Host "  Region: $Region" -ForegroundColor White
    Write-Host ""
    
    # Get stack outputs
    Write-Host "Stack Outputs:" -ForegroundColor Cyan
    aws cloudformation describe-stacks `
        --stack-name domain-ping-monitor `
        --query 'Stacks[0].Outputs' `
        --output table `
        --region $Region
    
    Write-Host ""
    Write-Host "Function Details:" -ForegroundColor Cyan
    aws lambda get-function `
        --function-name domain-ping-monitor `
        --query 'Configuration.[FunctionName,Runtime,Timeout,MemorySize,LastModified]' `
        --output table `
        --region $Region
    
    Write-Host ""
    Write-Host "Notification Channels:" -ForegroundColor Cyan
    Write-Host "  Email: Enabled (SNS)" -ForegroundColor White
    Write-Host "  Teams: $(if ($TeamsWebhookUrl) { 'Enabled' } else { 'Disabled' })" -ForegroundColor White
    Write-Host "  Slack: $(if ($SlackWebhookUrl) { 'Enabled' } else { 'Disabled' })" -ForegroundColor White
    Write-Host "  AI Agent: $(if ($AgentRuntimeArn) { 'Enabled' } else { 'Disabled' })" -ForegroundColor White
    Write-Host ""
    
    # Test invoke
    Write-Host "Testing function invocation..." -ForegroundColor Yellow
    $testResult = aws lambda invoke `
        --function-name domain-ping-monitor `
        --region $Region `
        --log-type Tail `
        /dev/null 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Test invocation successful!" -ForegroundColor Green
    } else {
        Write-Host "  Test invocation failed - check CloudWatch logs" -ForegroundColor Yellow
    }
    
} else {
    Write-Host ""
    Write-Host "=====================================" -ForegroundColor Red
    Write-Host "Deployment Failed!" -ForegroundColor Red
    Write-Host "=====================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Check CloudFormation console for details:" -ForegroundColor Yellow
    Write-Host "  https://console.aws.amazon.com/cloudformation" -ForegroundColor White
    exit 1
}