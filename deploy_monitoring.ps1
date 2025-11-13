# Deploy AWS CloudOps Agent Monitoring Infrastructure

param(
    [Parameter(Mandatory=$true)]
    [string]$NotificationEmail,
    
    [Parameter(Mandatory=$false)]
    [string]$Region = "us-east-1"
)

Write-Host "🚀 Deploying AWS CloudOps Agent Monitoring Infrastructure" -ForegroundColor Cyan

# Deploy monitoring stack
Write-Host "`n📦 Deploying monitoring stack..." -ForegroundColor Yellow
aws cloudformation create-stack `
    --stack-name cloudops-monitoring `
    --template-body file://infrastructure/monitoring_stack.yaml `
    --parameters ParameterKey=NotificationEmail,ParameterValue=$NotificationEmail `
    --capabilities CAPABILITY_NAMED_IAM `
    --region $Region

Write-Host "⏳ Waiting for stack creation..." -ForegroundColor Yellow
aws cloudformation wait stack-create-complete `
    --stack-name cloudops-monitoring `
    --region $Region

# Get Lambda ARN
$LambdaArn = aws cloudformation describe-stacks `
    --stack-name cloudops-monitoring `
    --query "Stacks[0].Outputs[?OutputKey=='MonitoringLambdaArn'].OutputValue" `
    --output text `
    --region $Region

Write-Host "✅ Monitoring stack deployed. Lambda ARN: $LambdaArn" -ForegroundColor Green

# Deploy EventBridge rules
Write-Host "`n📦 Deploying EventBridge rules..." -ForegroundColor Yellow
aws cloudformation create-stack `
    --stack-name cloudops-eventbridge `
    --template-body file://infrastructure/eventbridge_rules.yaml `
    --parameters ParameterKey=MonitoringLambdaArn,ParameterValue=$LambdaArn `
    --region $Region

Write-Host "⏳ Waiting for EventBridge stack..." -ForegroundColor Yellow
aws cloudformation wait stack-create-complete `
    --stack-name cloudops-eventbridge `
    --region $Region

Write-Host "`n✅ Monitoring infrastructure deployed successfully!" -ForegroundColor Green
Write-Host "`n📧 Check your email ($NotificationEmail) to confirm SNS subscription" -ForegroundColor Cyan
Write-Host "`n📊 Next steps:" -ForegroundColor Yellow
Write-Host "  1. Confirm SNS email subscription"
Write-Host "  2. Test monitoring: uv run src/workflows/scheduled_monitor.py"
Write-Host "  3. View logs: aws logs tail /aws/cloudops-agent/monitoring --follow"
