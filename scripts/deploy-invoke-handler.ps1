#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Deploy AWS CloudOps Invoke Handler Lambda function via CloudFormation

.DESCRIPTION
    This script automates the deployment of the Lambda invoke handler that receives
    service issues from monitoring Lambdas and invokes the AI agent for analysis.
    
    Steps performed:
    1. Create Lambda deployment package (zip)
    2. Upload to S3
    3. Deploy or update CloudFormation stack
    4. Monitor deployment status

.PARAMETER S3Bucket
    S3 bucket name for Lambda deployment package storage
    Default: aws-cloudops-deployment-<AccountId>

.PARAMETER StackName
    CloudFormation stack name
    Default: invoke-handler-stack

.PARAMETER Region
    AWS region for deployment
    Default: ap-southeast-1

.PARAMETER CreateS3Bucket
    Whether to create a new S3 bucket for analysis storage
    Default: true

.PARAMETER CreateDynamoDBTable
    Whether to create a DynamoDB table for alert tracking
    Default: false

.EXAMPLE
    .\deploy-invoke-handler.ps1
    
.EXAMPLE
    .\deploy-invoke-handler.ps1 -S3Bucket my-lambda-bucket -StackName my-stack
    
.EXAMPLE
    .\deploy-invoke-handler.ps1 -CreateDynamoDBTable true
#>

param(
    [string]$S3Bucket = "",
    [string]$StackName = "aws-cloudops-agent-invoke-handler-stack",
    [string]$Region = "ap-southeast-1",
    [string]$CreateS3Bucket = "true",
    [string]$CreateDynamoDBTable = "false"
)

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Write-Step {
    param([string]$Message)
    Write-Host "`n==> $Message" -ForegroundColor Blue
}

# Get script directory and workspace root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WorkspaceRoot = Split-Path -Parent $ScriptDir

Write-Info "AWS CloudOps Invoke Handler Deployment Script"
Write-Info "=============================================="
Write-Info "Region: $Region"
Write-Info "Stack Name: $StackName"

# Step 1: Get AWS Account ID
Write-Step "Getting AWS Account ID..."
try {
    $AccountId = aws sts get-caller-identity --query Account --output text
    if ($LASTEXITCODE -ne 0) { throw "Failed to get AWS account ID" }
    Write-Success "Account ID: $AccountId"
} catch {
    Write-Error "Failed to authenticate with AWS. Please configure AWS CLI credentials."
    exit 1
}

# Set default S3 bucket if not provided
if ([string]::IsNullOrEmpty($S3Bucket)) {
    $S3Bucket = "aws-cloudops-deployment-$AccountId"
    Write-Info "Using default S3 bucket: $S3Bucket"
}

# Step 2: Check if S3 bucket exists, create if needed
Write-Step "Checking S3 bucket: $S3Bucket..."
$PreviousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$null = aws s3api head-bucket --bucket $S3Bucket 2>&1
$BucketCheckExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorPreference

if ($BucketCheckExitCode -ne 0) {
    Write-Warning "S3 bucket does not exist. Creating..."
    if ($Region -eq "us-east-1") {
        aws s3api create-bucket --bucket $S3Bucket --region $Region | Out-Null
    } else {
        aws s3api create-bucket --bucket $S3Bucket --region $Region --create-bucket-configuration LocationConstraint=$Region | Out-Null
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Success "S3 bucket created: $S3Bucket"
    } else {
        Write-Error "Failed to create S3 bucket"
        exit 1
    }
} else {
    Write-Success "S3 bucket exists: $S3Bucket"
}

# Step 3: Create Lambda deployment package
Write-Step "Creating Lambda deployment package..."
$LambdaSourcePath = Join-Path $WorkspaceRoot "src\lambdas\lambda_invoke_handler.py"
$TempDir = Join-Path $env:TEMP "lambda-invoke-handler-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
$ZipPath = Join-Path $TempDir "lambda_invoke_handler.zip"

try {
    # Create temp directory
    New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
    
    # Copy Lambda file to temp directory
    Copy-Item -Path $LambdaSourcePath -Destination $TempDir
    
    # Create zip file
    $LambdaFile = Join-Path $TempDir "lambda_invoke_handler.py"
    Compress-Archive -Path $LambdaFile -DestinationPath $ZipPath -Force
    
    $ZipSize = (Get-Item $ZipPath).Length
    Write-Success "Deployment package created: $ZipPath ($([math]::Round($ZipSize/1KB, 2)) KB)"
} catch {
    Write-Error "Failed to create deployment package: $_"
    exit 1
}

# Step 4: Upload to S3
Write-Step "Uploading deployment package to S3..."
$S3Key = "invoke-handler/lambda_invoke_handler.zip"
try {
    aws s3 cp $ZipPath "s3://$S3Bucket/$S3Key" --region $Region
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Uploaded to s3://$S3Bucket/$S3Key"
    } else {
        throw "S3 upload failed"
    }
} catch {
    Write-Error "Failed to upload to S3: $_"
    exit 1
} finally {
    # Clean up temp directory
    Remove-Item -Path $TempDir -Recurse -Force -ErrorAction SilentlyContinue
}

# Step 5: Check if stack exists
Write-Step "Checking if CloudFormation stack exists..."
$PreviousErrorPreference = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
$null = aws cloudformation describe-stacks --stack-name $StackName --region $Region 2>&1
$StackCheckExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorPreference
$IsUpdate = $StackCheckExitCode -eq 0

if ($IsUpdate) {
    Write-Info "Stack exists. Will perform UPDATE operation."
    $Operation = "update-stack"
} else {
    Write-Info "Stack does not exist. Will perform CREATE operation."
    $Operation = "create-stack"
}

# Step 6: Deploy CloudFormation stack
Write-Step "Deploying CloudFormation stack..."
$TemplatePath = Join-Path $WorkspaceRoot "cloudformation\invoke-handler.yaml"

$Parameters = @(
    "ParameterKey=LambdaDeploymentBucket,ParameterValue=$S3Bucket",
    "ParameterKey=LambdaDeploymentKey,ParameterValue=$S3Key",
    "ParameterKey=CreateS3Bucket,ParameterValue=$CreateS3Bucket",
    "ParameterKey=CreateDynamoDBTable,ParameterValue=$CreateDynamoDBTable"
)

try {
    if ($Operation -eq "create-stack") {
        $StackId = aws cloudformation create-stack `
            --stack-name $StackName `
            --template-body "file://$TemplatePath" `
            --parameters $Parameters `
            --capabilities CAPABILITY_NAMED_IAM `
            --region $Region `
            --output text
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Stack creation initiated"
            Write-Info "Stack ID: $StackId"
        } else {
            throw "Stack creation failed"
        }
    } else {
        aws cloudformation update-stack `
            --stack-name $StackName `
            --template-body "file://$TemplatePath" `
            --parameters $Parameters `
            --capabilities CAPABILITY_NAMED_IAM `
            --region $Region
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Stack update initiated"
        } elseif ($LASTEXITCODE -eq 254) {
            Write-Warning "No updates to perform (stack is already up to date)"
            exit 0
        } else {
            throw "Stack update failed"
        }
    }
} catch {
    Write-Error "Failed to deploy stack: $_"
    exit 1
}

# Step 7: Monitor stack status
Write-Step "Monitoring stack deployment (this may take a few minutes)..."
$Status = ""
$PreviousStatus = ""
$MaxAttempts = 60  # 5 minutes max (5 second intervals)
$Attempt = 0

while ($Attempt -lt $MaxAttempts) {
    Start-Sleep -Seconds 5
    $Attempt++
    
    $StackInfo = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query 'Stacks[0].[StackStatus,StackStatusReason]' `
        --output json | ConvertFrom-Json
    
    $Status = $StackInfo[0]
    $StatusReason = $StackInfo[1]
    
    if ($Status -ne $PreviousStatus) {
        Write-Info "Stack Status: $Status"
        if ($StatusReason) {
            Write-Info "Reason: $StatusReason"
        }
        $PreviousStatus = $Status
    }
    
    # Check for completion
    if ($Status -match "COMPLETE$") {
        if ($Status -match "^(CREATE|UPDATE)_COMPLETE$") {
            Write-Success "Stack deployment completed successfully!"
            break
        } elseif ($Status -eq "ROLLBACK_COMPLETE") {
            Write-Error "Stack deployment failed and rolled back"
            break
        }
    } elseif ($Status -match "FAILED$") {
        Write-Error "Stack deployment failed: $Status"
        break
    }
}

if ($Attempt -ge $MaxAttempts) {
    Write-Warning "Timeout waiting for stack deployment. Status: $Status"
}

# Step 8: Display stack outputs
if ($Status -match "^(CREATE|UPDATE)_COMPLETE$") {
    Write-Step "Stack Outputs:"
    aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue,Description]' `
        --output table
    
    Write-Success "`nDeployment completed successfully!"
    Write-Info "`nLambda Function: aws-cloudops-invoke-handler"
    Write-Info "Region: $Region"
    Write-Info "Stack: $StackName"
    
    # Get function ARN
    $FunctionArn = aws cloudformation describe-stacks `
        --stack-name $StackName `
        --region $Region `
        --query 'Stacks[0].Outputs[?OutputKey==`FunctionArn`].OutputValue' `
        --output text
    
    if ($FunctionArn) {
        Write-Info "`nFunction ARN: $FunctionArn"
        Write-Info "`nTest the function:"
        Write-Host "aws lambda invoke --function-name aws-cloudops-invoke-handler ``" -ForegroundColor Gray
        Write-Host "  --payload '{""service_name"":""test-service"",""service_type"":""Test"",""error_details"":""Test error""}' ``" -ForegroundColor Gray
        Write-Host "  --region $Region ``" -ForegroundColor Gray
        Write-Host "  response.json" -ForegroundColor Gray
    }
} else {
    Write-Error "`nDeployment failed. Check CloudFormation events for details:"
    Write-Host "aws cloudformation describe-stack-events --stack-name $StackName --region $Region --max-items 10" -ForegroundColor Gray
    exit 1
}
