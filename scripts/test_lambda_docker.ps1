#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Test Lambda function using AWS SAM CLI or Docker
.DESCRIPTION
    This script helps test the Lambda function locally using either:
    1. AWS SAM CLI (Serverless Application Model)
    2. Docker with Lambda runtime image
#>

param(
    [string]$Method = "sam",  # "sam" or "docker"
    [string]$TeamsWebhook = "",
    [string]$SlackWebhook = "",
    [string]$AgentArn = "",
    [switch]$SkipSNS
)

Write-Host "Lambda Local Testing Utility" -ForegroundColor Cyan
Write-Host "=============================" -ForegroundColor Cyan
Write-Host ""

# Check if running method is available
if ($Method -eq "sam") {
    $samInstalled = Get-Command sam -ErrorAction SilentlyContinue
    if (-not $samInstalled) {
        Write-Host "AWS SAM CLI not found. Please install it:" -ForegroundColor Red
        Write-Host "  https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Or use Docker method: .\test_lambda_docker.ps1 -Method docker" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Using AWS SAM CLI for local testing" -ForegroundColor Green
    Write-Host ""
    
    # Create SAM template
    $samTemplate = @"
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  PingMonitorFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: .
      Handler: src.lambda_ping_monitor.lambda_handler
      Runtime: python3.11
      Timeout: 90
      MemorySize: 256
      Environment:
        Variables:
          SNS_TOPIC_ARN: $(if ($SkipSNS) { '' } else { 'arn:aws:sns:ap-southeast-1:010382427026:domain-alerts' })
          TEAMS_WEBHOOK_URL: $TeamsWebhook
          SLACK_WEBHOOK_URL: $SlackWebhook
          AGENT_RUNTIME_ARN: $AgentArn
          COGNITO_USERNAME: ted8hc
          COGNITO_PASSWORD: 
          COGNITO_CLIENT_ID: 40ede8sr0l0bs37hps0lbgvr8p
"@
    
    $samTemplate | Out-File -FilePath "template-test.yaml" -Encoding UTF8
    
    Write-Host "Invoking function with SAM CLI..." -ForegroundColor Yellow
    sam local invoke PingMonitorFunction --template template-test.yaml --event test-event.json
    
    # Cleanup
    Remove-Item "template-test.yaml" -ErrorAction SilentlyContinue
    
} elseif ($Method -eq "docker") {
    $dockerInstalled = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerInstalled) {
        Write-Host "Docker not found. Please install Docker Desktop:" -ForegroundColor Red
        Write-Host "  https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "Using Docker with Lambda runtime image" -ForegroundColor Green
    Write-Host ""
    
    # Create test event
    $testEvent = @{
        "source" = "local-test"
        "detail-type" = "Scheduled Event"
    } | ConvertTo-Json
    
    # Build environment variables
    $envVars = @(
        "-e", "SNS_TOPIC_ARN=$(if ($SkipSNS) { '' } else { 'arn:aws:sns:ap-southeast-1:010382427026:domain-alerts' })",
        "-e", "TEAMS_WEBHOOK_URL=$TeamsWebhook",
        "-e", "SLACK_WEBHOOK_URL=$SlackWebhook",
        "-e", "AGENT_RUNTIME_ARN=$AgentArn",
        "-e", "COGNITO_USERNAME=ted8hc",
        "-e", "COGNITO_PASSWORD=",
        "-e", "COGNITO_CLIENT_ID=40ede8sr0l0bs37hps0lbgvr8p",
        "-e", "AWS_REGION=ap-southeast-1",
        "-e", "AWS_DEFAULT_REGION=ap-southeast-1"
    )
    
    Write-Host "Building Lambda deployment package..." -ForegroundColor Yellow
    
    # Create package directory
    if (Test-Path "test-package") {
        Remove-Item -Recurse -Force "test-package"
    }
    New-Item -ItemType Directory -Path "test-package" | Out-Null
    
    # Install dependencies
    pip install --target test-package requests boto3 -q
    Copy-Item "src\lambda_ping_monitor.py" -Destination "test-package"
    
    Write-Host "Starting Lambda runtime container..." -ForegroundColor Yellow
    
    # Run Lambda in Docker
    docker run --rm `
        $envVars `
        -v "${PWD}/test-package:/var/task:ro" `
        -p 9000:8080 `
        public.ecr.aws/lambda/python:3.11 `
        lambda_ping_monitor.lambda_handler
    
    # Cleanup
    Remove-Item -Recurse -Force "test-package" -ErrorAction SilentlyContinue
    
} else {
    Write-Host "Invalid method: $Method" -ForegroundColor Red
    Write-Host "Use 'sam' or 'docker'" -ForegroundColor Yellow
}
