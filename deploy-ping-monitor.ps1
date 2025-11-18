#!/usr/bin/env pwsh

Write-Host "Deploying Domain Ping Monitor..." -ForegroundColor Green

# Deploy CloudFormation stack
aws cloudformation deploy `
    --template-file cloudformation/ping-monitor.yaml `
    --stack-name domain-ping-monitor `
    --capabilities CAPABILITY_IAM `
    --region ap-southeast-1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Ping monitor deployed successfully!" -ForegroundColor Green
    Write-Host "Monitor will check nghuy.link every 5 minutes" -ForegroundColor Cyan
    
    # Get function details
    aws lambda get-function --function-name domain-ping-monitor --query 'Configuration.[FunctionName,Runtime,Timeout]' --output table --region ap-southeast-1
} else {
    Write-Host "Deployment failed!" -ForegroundColor Red
}