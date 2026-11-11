#!/bin/bash

set -e

ZIP_FILE="lambda-execute-deployment.zip"
HANDLER_FILE="lambda_execution_handler_copy.py"

# === Update these values ===
BUCKET_NAME="lambda-zip-uupload-quan"
S3_REGION="ap-southeast-1"       # region of your S3 bucket
LAMBDA_NAME="central-lambda-execution_handler"
LAMBDA_REGION="ap-southeast-2"   # region where the Lambda function lives

echo "[1] Removing old ZIP..."
rm -f "$ZIP_FILE"

echo "[2] Creating new ZIP..."
zip "$ZIP_FILE" "$HANDLER_FILE"

echo "[3] Uploading ZIP to S3 ($S3_REGION)..."
aws s3 cp "$ZIP_FILE" "s3://$BUCKET_NAME/$ZIP_FILE" --region "$S3_REGION"

echo "[4] Updating Lambda function code in region $LAMBDA_REGION..."
aws lambda update-function-code \
    --function-name "$LAMBDA_NAME" \
    --s3-bucket "$BUCKET_NAME" \
    --s3-key "$ZIP_FILE" \
    --region "$LAMBDA_REGION"

echo "✅ Deployment complete! Lambda updated from S3 cross-region."