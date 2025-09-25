#!/bin/bash
# Deploy DynamoDB table for RAG system

STACK_NAME="aws-cloudops-rag-stack"
TEMPLATE_FILE="dynamodb-rag.yaml"

echo "🚀 Deploying DynamoDB table for RAG system..."

aws cloudformation deploy \
  --template-file $TEMPLATE_FILE \
  --stack-name $STACK_NAME \
  --no-fail-on-empty-changeset

echo "✅ Deployment complete!"
echo "📋 Table name: aws-cloudops-knowledge"