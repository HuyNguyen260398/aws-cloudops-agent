# PowerShell script to package AWS CloudOps Agent for Lambda deployment
param(
    [string]$OutputFile = "aws-cloudops-agent-lambda.zip",
    [switch]$Clean = $false
)

Write-Host "AWS CloudOps Agent Lambda Deployment Packager" -ForegroundColor Blue
Write-Host "=============================================" -ForegroundColor Blue

# Create temporary directory for packaging
$TempDir = "lambda-package-temp"
$CurrentDir = Get-Location

if ($Clean -and (Test-Path $TempDir)) {
    Write-Host "Cleaning up existing temp directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $TempDir
}

if ($Clean -and (Test-Path $OutputFile)) {
    Write-Host "Removing existing package file..." -ForegroundColor Yellow
    Remove-Item -Force $OutputFile
}

try {
    # Create temp directory
    Write-Host "Creating temporary package directory..." -ForegroundColor Green
    New-Item -ItemType Directory -Force -Path $TempDir | Out-Null
    
    # Copy source files
    Write-Host "Copying source files..." -ForegroundColor Green
    Copy-Item "lambda_handler.py" "$TempDir/"
    Copy-Item "src" "$TempDir/" -Recurse
    
    # Install dependencies to temp directory
    Write-Host "Installing dependencies..." -ForegroundColor Green
    $requirements = @(
        "boto3",
        "strands-agents",
        "strands-agents-tools"
    )
    
    foreach ($package in $requirements) {
        Write-Host "  Installing $package..." -ForegroundColor Cyan
        & pip install $package --target "$TempDir" 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to install $package"
            exit 1
        }
    }
    
    # Create the zip file
    Write-Host "Creating deployment package..." -ForegroundColor Green
    Push-Location $TempDir
    
    # Use PowerShell's Compress-Archive
    $files = Get-ChildItem -Recurse
    Compress-Archive -Path * -DestinationPath "../$OutputFile" -Force
    
    Pop-Location
    
    # Get file size
    $FileSize = (Get-Item $OutputFile).Length
    $FileSizeMB = [math]::Round($FileSize / 1MB, 2)
    
    Write-Host "Package created successfully!" -ForegroundColor Green
    Write-Host "   File: $OutputFile" -ForegroundColor White
    Write-Host "   Size: $FileSizeMB MB" -ForegroundColor White
    
    if ($FileSizeMB -gt 50) {
        Write-Warning "Package size is over 50MB. Consider using Lambda Layers for large dependencies."
    }
    
    # Check Lambda limits
    if ($FileSizeMB -gt 250) {
        Write-Error "Package size exceeds Lambda 250MB limit for deployment packages!"
        exit 1
    }
    
} catch {
    Write-Error "Failed to create deployment package: $_"
    exit 1
} finally {
    # Cleanup
    if (Test-Path $TempDir) {
        Write-Host "Cleaning up temporary files..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force $TempDir
    }
}

Write-Host ""
Write-Host "Deployment package ready!" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Upload $OutputFile to AWS Lambda" -ForegroundColor White
Write-Host "2. Set handler to: lambda_handler.lambda_handler" -ForegroundColor White
Write-Host "3. Configure environment variables if needed" -ForegroundColor White
Write-Host "4. Set appropriate IAM permissions" -ForegroundColor White