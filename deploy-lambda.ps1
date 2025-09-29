# AWS CloudOps Agent Lambda Deployment Script
# Deploys the AWS CloudOps Agent to AWS Lambda with API Gateway

param(
    [string]$FunctionName = "aws-cloudops-agent",
    [string]$Region = "ap-southeast-1",
    [string]$Profile = "default",
    [switch]$SkipInfrastructure,
    [switch]$UpdateCodeOnly,
    [switch]$Help
)

if ($Help) {
    Write-Host @"
AWS CloudOps Agent Lambda Deployment Script

USAGE:
    .\deploy-lambda.ps1 [OPTIONS]

OPTIONS:
    -FunctionName <name>     Name for the Lambda function (default: aws-cloudops-agent)
    -Region <region>         AWS region for deployment (default: ap-southeast-1)
    -Profile <profile>       AWS CLI profile to use (default: default)
    -SkipInfrastructure      Skip CloudFormation stack creation/update
    -UpdateCodeOnly          Only update the Lambda function code
    -Help                    Show this help message

EXAMPLES:
    # Full deployment with default settings
    .\deploy-lambda.ps1

    # Deploy to specific region with custom function name
    .\deploy-lambda.ps1 -FunctionName "my-cloudops-agent" -Region "us-west-2"

    # Update only the Lambda function code (skip infrastructure)
    .\deploy-lambda.ps1 -UpdateCodeOnly

REQUIREMENTS:
    - AWS CLI configured with appropriate credentials
    - Python 3.11+ installed
    - pip package manager
    - PowerShell 5.1+
"@
    exit 0
}

# Configuration
$STACK_NAME = "$FunctionName-stack"
$DEPLOYMENT_BUCKET = "$FunctionName-deployment-$(Get-Random -Minimum 1000 -Maximum 9999)"
$ZIP_FILE = "lambda-deployment.zip"
$TEMP_DIR = "temp-lambda-build"

Write-Host "🚀 AWS CloudOps Agent Lambda Deployment" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "Function Name: $FunctionName" -ForegroundColor Green
Write-Host "Region: $Region" -ForegroundColor Green
Write-Host "AWS Profile: $Profile" -ForegroundColor Green
Write-Host ""

# Function to check if AWS CLI is configured
function Test-AwsConfiguration {
    try {
        $identity = aws sts get-caller-identity --profile $Profile --region $Region 2>$null | ConvertFrom-Json
        if ($identity) {
            Write-Host "✅ AWS CLI configured - Account: $($identity.Account), User: $($identity.Arn)" -ForegroundColor Green
            return $true
        }
    }
    catch {
        Write-Host "❌ AWS CLI not configured or invalid credentials" -ForegroundColor Red
        Write-Host "Please run: aws configure --profile $Profile" -ForegroundColor Yellow
        return $false
    }
    return $false
}

# Function to create deployment package
function New-LambdaDeploymentPackage {
    Write-Host "📦 Creating Lambda deployment package..." -ForegroundColor Yellow
    
    # Clean up previous build
    if (Test-Path $TEMP_DIR) {
        Remove-Item -Recurse -Force $TEMP_DIR
    }
    if (Test-Path $ZIP_FILE) {
        Remove-Item -Force $ZIP_FILE
    }
    
    # Create temporary build directory
    $null = New-Item -ItemType Directory -Path $TEMP_DIR -Force
    
    # Copy source code
    Copy-Item -Path "src" -Destination "$TEMP_DIR\src" -Recurse
    Copy-Item -Path "lambda_handler.py" -Destination "$TEMP_DIR\"
    
    # Install dependencies
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    Push-Location $TEMP_DIR
    
    try {
        # Create virtual environment
        python -m venv lambda-env
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment"
        }
        
        # Activate virtual environment
        & "lambda-env\Scripts\Activate.ps1"
        
        # Install dependencies
        pip install --no-cache-dir -r "..\requirements-lambda.txt" -t .
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install dependencies"
        }
        
        # Deactivate virtual environment
        deactivate
        
        # Remove virtual environment directory
        Remove-Item -Recurse -Force "lambda-env"
        
        # Create ZIP file
        Write-Host "🗜️ Creating deployment ZIP..." -ForegroundColor Yellow
        Compress-Archive -Path "*" -DestinationPath "..\$ZIP_FILE" -Force
        
        Pop-Location
        
        # Clean up temp directory
        Remove-Item -Recurse -Force $TEMP_DIR
        
        $zipSize = (Get-Item $ZIP_FILE).Length / 1MB
        Write-Host "✅ Deployment package created: $ZIP_FILE ($([math]::Round($zipSize, 2)) MB)" -ForegroundColor Green
        
    }
    catch {
        Pop-Location
        if (Test-Path $TEMP_DIR) {
            Remove-Item -Recurse -Force $TEMP_DIR
        }
        Write-Host "❌ Failed to create deployment package: $_" -ForegroundColor Red
        exit 1
    }
}

# Function to create S3 bucket for deployment
function New-DeploymentBucket {
    Write-Host "🪣 Creating S3 deployment bucket..." -ForegroundColor Yellow
    
    try {
        # Check if bucket exists
        $bucketExists = aws s3api head-bucket --bucket $DEPLOYMENT_BUCKET --profile $Profile --region $Region 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Deployment bucket already exists: $DEPLOYMENT_BUCKET" -ForegroundColor Green
            return
        }
        
        # Create bucket
        if ($Region -eq "us-east-1") {
            aws s3api create-bucket --bucket $DEPLOYMENT_BUCKET --profile $Profile --region $Region | Out-Null
        } else {
            aws s3api create-bucket --bucket $DEPLOYMENT_BUCKET --profile $Profile --region $Region --create-bucket-configuration LocationConstraint=$Region | Out-Null
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Deployment bucket created: $DEPLOYMENT_BUCKET" -ForegroundColor Green
        } else {
            throw "Failed to create S3 bucket"
        }
    }
    catch {
        Write-Host "❌ Failed to create deployment bucket: $_" -ForegroundColor Red
        exit 1
    }
}

# Function to upload deployment package
function Publish-DeploymentPackage {
    Write-Host "⬆️ Uploading deployment package to S3..." -ForegroundColor Yellow
    
    try {
        aws s3 cp $ZIP_FILE "s3://$DEPLOYMENT_BUCKET/$ZIP_FILE" --profile $Profile --region $Region
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Deployment package uploaded successfully" -ForegroundColor Green
        } else {
            throw "Failed to upload deployment package"
        }
    }
    catch {
        Write-Host "❌ Failed to upload deployment package: $_" -ForegroundColor Red
        exit 1
    }
}

# Function to deploy infrastructure
function Deploy-Infrastructure {
    Write-Host "🏗️ Deploying infrastructure with CloudFormation..." -ForegroundColor Yellow
    
    try {
        aws cloudformation deploy `
            --template-file "inf\lambda-infrastructure.yaml" `
            --stack-name $STACK_NAME `
            --parameter-overrides FunctionName=$FunctionName `
            --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM `
            --profile $Profile `
            --region $Region `
            --no-fail-on-empty-changeset
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Infrastructure deployed successfully" -ForegroundColor Green
        } else {
            throw "CloudFormation deployment failed"
        }
    }
    catch {
        Write-Host "❌ Failed to deploy infrastructure: $_" -ForegroundColor Red
        exit 1
    }
}

# Function to update Lambda function code
function Update-LambdaCode {
    Write-Host "🔄 Updating Lambda function code..." -ForegroundColor Yellow
    
    try {
        aws lambda update-function-code `
            --function-name $FunctionName `
            --s3-bucket $DEPLOYMENT_BUCKET `
            --s3-key $ZIP_FILE `
            --profile $Profile `
            --region $Region | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Lambda function code updated successfully" -ForegroundColor Green
        } else {
            throw "Failed to update Lambda function code"
        }
    }
    catch {
        Write-Host "❌ Failed to update Lambda function code: $_" -ForegroundColor Red
        exit 1
    }
}

# Function to get deployment outputs
function Get-DeploymentOutputs {
    Write-Host "Getting deployment information..." -ForegroundColor Yellow
    
    try {
        $outputs = aws cloudformation describe-stacks `
            --stack-name $STACK_NAME `
            --profile $Profile `
            --region $Region `
            --query "Stacks[0].Outputs" 2>$null | ConvertFrom-Json
        
        if ($outputs) {
            Write-Host ""
            Write-Host "Deployment Complete!" -ForegroundColor Green
            Write-Host "===================" -ForegroundColor Green
            
            foreach ($output in $outputs) {
                switch ($output.OutputKey) {
                    "ApiGatewayUrl" { 
                        Write-Host "API Gateway URL: $($output.OutputValue)" -ForegroundColor Cyan 
                    }
                    "ChatEndpoint" { 
                        Write-Host "Chat Endpoint: $($output.OutputValue)" -ForegroundColor Cyan 
                    }
                    "HealthEndpoint" { 
                        Write-Host "Health Check: $($output.OutputValue)" -ForegroundColor Cyan 
                    }
                    "LambdaFunctionName" { 
                        Write-Host "Function Name: $($output.OutputValue)" -ForegroundColor Cyan 
                    }
                }
            }
            
            Write-Host ""
            Write-Host "Test your deployment using curl or PowerShell Invoke-RestMethod" -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "Deployment completed but failed to get outputs: $_" -ForegroundColor Yellow
    }
}

# Main deployment logic
try {
    # Check prerequisites
    if (-not (Test-AwsConfiguration)) {
        exit 1
    }
    
    # Create deployment package
    New-LambdaDeploymentPackage
    
    # Create S3 bucket and upload package
    New-DeploymentBucket
    Publish-DeploymentPackage
    
    if ($UpdateCodeOnly) {
        # Only update Lambda function code
        Update-LambdaCode
        Write-Host "✅ Lambda function code updated successfully!" -ForegroundColor Green
    } else {
        # Deploy infrastructure (unless skipped)
        if (-not $SkipInfrastructure) {
            Deploy-Infrastructure
        }
        
        # Update Lambda function code
        Update-LambdaCode
        
        # Get deployment outputs
        Get-DeploymentOutputs
    }
    
    # Cleanup
    if (Test-Path $ZIP_FILE) {
        Remove-Item -Force $ZIP_FILE
    }
    
    Write-Host ""
    Write-Host "🚀 AWS CloudOps Agent deployed successfully!" -ForegroundColor Green
    
} catch {
    Write-Host "❌ Deployment failed: $_" -ForegroundColor Red
    
    # Cleanup on failure
    if (Test-Path $TEMP_DIR) {
        Remove-Item -Recurse -Force $TEMP_DIR
    }
    if (Test-Path $ZIP_FILE) {
        Remove-Item -Force $ZIP_FILE
    }
    
    exit 1
}