# PowerShell script to deploy AWS CloudOps Agent to Lambda
param(
    [string]$StackName = "aws-cloudops-agent-stack",
    [string]$FunctionName = "aws-cloudops-agent",
    [string]$Region = "ap-southeast-1",
    [string]$Profile = "default",
    [int]$Timeout = 300,
    [int]$MemorySize = 512,
    [switch]$SkipPackaging = $false,
    [switch]$UpdateStack = $false
)

Write-Host "🚀 AWS CloudOps Agent Lambda Deployment" -ForegroundColor Blue
Write-Host "=======================================" -ForegroundColor Blue

$PackageFile = "aws-cloudops-agent-lambda.zip"

# Check if AWS CLI is installed
try {
    $awsVersion = aws --version 2>$null
    Write-Host "✅ AWS CLI detected: $($awsVersion.Split()[0])" -ForegroundColor Green
} catch {
    Write-Error "❌ AWS CLI not found. Please install AWS CLI first."
    exit 1
}

# Set AWS profile if specified
if ($Profile -ne "default") {
    $env:AWS_PROFILE = $Profile
    Write-Host "🔧 Using AWS profile: $Profile" -ForegroundColor Yellow
}

# Step 1: Package the Lambda function
if (-not $SkipPackaging) {
    Write-Host ""
    Write-Host "📦 Step 1: Packaging Lambda function..." -ForegroundColor Cyan
    
    if (Test-Path "package-lambda.ps1") {
        & .\package-lambda.ps1 -OutputFile $PackageFile -Clean
        if ($LASTEXITCODE -ne 0) {
            Write-Error "❌ Failed to package Lambda function"
            exit 1
        }
    } else {
        Write-Error "❌ package-lambda.ps1 not found. Please run this script from the project root."
        exit 1
    }
} else {
    Write-Host "⏭️ Skipping packaging (using existing $PackageFile)" -ForegroundColor Yellow
    if (-not (Test-Path $PackageFile)) {
        Write-Error "❌ Package file $PackageFile not found. Run without -SkipPackaging to create it."
        exit 1
    }
}

# Step 2: Check if stack exists
Write-Host ""
Write-Host "🔍 Step 2: Checking if CloudFormation stack exists..." -ForegroundColor Cyan

$stackExists = $false
try {
    $stackStatus = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].StackStatus' --output text 2>$null
    if ($LASTEXITCODE -eq 0) {
        $stackExists = $true
        Write-Host "📋 Stack '$StackName' exists with status: $stackStatus" -ForegroundColor Yellow
    }
} catch {
    Write-Host "📋 Stack '$StackName' does not exist" -ForegroundColor Green
}

# Step 3: Deploy or update CloudFormation stack
Write-Host ""
if ($stackExists -and -not $UpdateStack) {
    Write-Host "⚠️ Stack already exists. Use -UpdateStack to update it." -ForegroundColor Yellow
} else {
    $action = if ($stackExists) { "Updating" } else { "Creating" }
    Write-Host "☁️ Step 3: $action CloudFormation stack..." -ForegroundColor Cyan
    
    $templateFile = "cloudformation-template.yaml"
    if (-not (Test-Path $templateFile)) {
        Write-Error "❌ CloudFormation template $templateFile not found"
        exit 1
    }
    
    $deployCmd = if ($stackExists) { "update-stack" } else { "create-stack" }
    
    try {
        aws cloudformation $deployCmd `
            --stack-name $StackName `
            --template-body "file://$templateFile" `
            --parameters "ParameterKey=FunctionName,ParameterValue=$FunctionName" "ParameterKey=Timeout,ParameterValue=$Timeout" "ParameterKey=MemorySize,ParameterValue=$MemorySize" `
            --capabilities CAPABILITY_NAMED_IAM `
            --region $Region
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "❌ Failed to deploy CloudFormation stack"
            exit 1
        }
        
        Write-Host "⏳ Waiting for stack deployment to complete..." -ForegroundColor Yellow
        aws cloudformation wait stack-$($deployCmd.Replace('-stack',''))-complete --stack-name $StackName --region $Region
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ CloudFormation stack deployed successfully!" -ForegroundColor Green
        } else {
            Write-Error "❌ Stack deployment failed or timed out"
            exit 1
        }
        
    } catch {
        Write-Error "❌ Failed to execute CloudFormation deployment: $_"
        exit 1
    }
}

# Step 4: Update Lambda function code
Write-Host ""
Write-Host "📤 Step 4: Updating Lambda function code..." -ForegroundColor Cyan

try {
    aws lambda update-function-code `
        --function-name $FunctionName `
        --zip-file "fileb://$PackageFile" `
        --region $Region
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Lambda function code updated successfully!" -ForegroundColor Green
    } else {
        Write-Error "❌ Failed to update Lambda function code"
        exit 1
    }
} catch {
    Write-Error "❌ Failed to update Lambda function: $_"
    exit 1
}

# Step 5: Get deployment info
Write-Host ""
Write-Host "📊 Step 5: Retrieving deployment information..." -ForegroundColor Cyan

try {
    $outputs = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query 'Stacks[0].Outputs' --output json | ConvertFrom-Json
    
    Write-Host ""
    Write-Host "🎉 Deployment completed successfully!" -ForegroundColor Green
    Write-Host "====================================" -ForegroundColor Green
    
    foreach ($output in $outputs) {
        $key = $output.OutputKey
        $value = $output.OutputValue
        $description = $output.Description
        
        Write-Host "$key : $value" -ForegroundColor White
        Write-Host "  $description" -ForegroundColor Gray
        Write-Host ""
    }
    
    # Test the function
    Write-Host "🧪 Testing the Lambda function..." -ForegroundColor Cyan
    $testPayload = @{
        message = "Hello, I am testing the AWS CloudOps Agent!"
    } | ConvertTo-Json
    
    $testResult = aws lambda invoke `
        --function-name $FunctionName `
        --payload $testPayload `
        --region $Region `
        test-output.json
    
    if ($LASTEXITCODE -eq 0 -and (Test-Path "test-output.json")) {
        $response = Get-Content "test-output.json" | ConvertFrom-Json
        Write-Host "✅ Test successful!" -ForegroundColor Green
        Write-Host "Response: $($response.body)" -ForegroundColor White
        Remove-Item "test-output.json" -ErrorAction SilentlyContinue
    } else {
        Write-Warning "⚠️ Function test failed, but deployment was successful"
    }
    
} catch {
    Write-Warning "⚠️ Could not retrieve deployment information: $_"
}

Write-Host ""
Write-Host "📝 Next steps:" -ForegroundColor Yellow
Write-Host "1. Test your Lambda function using the AWS Console or CLI" -ForegroundColor White
Write-Host "2. Configure any additional environment variables if needed" -ForegroundColor White
Write-Host "3. Set up monitoring and logging as required" -ForegroundColor White
Write-Host "4. Use the API Gateway URL to access via HTTP requests" -ForegroundColor White