#!/bin/bash
# AWS CloudOps Agent Lambda Deployment Script for Unix/Linux/macOS

set -e

# Default configuration
FUNCTION_NAME="${1:-aws-cloudops-agent}"
REGION="${2:-ap-southeast-1}"
PROFILE="${3:-default}"
STACK_NAME="${FUNCTION_NAME}-stack"
DEPLOYMENT_BUCKET="${FUNCTION_NAME}-deployment-$(date +%s)"
ZIP_FILE="lambda-deployment.zip"
TEMP_DIR="temp-lambda-build"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${CYAN}🚀 AWS CloudOps Agent Lambda Deployment${NC}"
    echo -e "${CYAN}=======================================${NC}"
    echo -e "${GREEN}Function Name: $FUNCTION_NAME${NC}"
    echo -e "${GREEN}Region: $REGION${NC}"
    echo -e "${GREEN}AWS Profile: $PROFILE${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}$1${NC}"
}

check_prerequisites() {
    print_info "🔍 Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI not found. Please install AWS CLI."
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found. Please install Python 3.11+."
        exit 1
    fi
    
    # Check AWS configuration
    if ! aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" &> /dev/null; then
        print_error "AWS CLI not configured or invalid credentials for profile '$PROFILE'"
        print_warning "Please run: aws configure --profile $PROFILE"
        exit 1
    fi
    
    local IDENTITY=$(aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" --output json)
    local ACCOUNT=$(echo "$IDENTITY" | jq -r '.Account')
    local USER_ARN=$(echo "$IDENTITY" | jq -r '.Arn')
    
    print_success "AWS CLI configured - Account: $ACCOUNT, User: $USER_ARN"
}

create_deployment_package() {
    print_info "📦 Creating Lambda deployment package..."
    
    # Clean up previous build
    rm -rf "$TEMP_DIR" "$ZIP_FILE"
    
    # Create temporary build directory
    mkdir "$TEMP_DIR"
    
    # Copy source code
    cp -r src "$TEMP_DIR/"
    cp lambda_handler.py "$TEMP_DIR/"
    
    # Install dependencies
    print_info "📥 Installing Python dependencies..."
    cd "$TEMP_DIR"
    
    # Install dependencies directly to current directory
    pip3 install --no-cache-dir -r ../requirements-lambda.txt -t .
    
    # Create ZIP file
    print_info "🗜️ Creating deployment ZIP..."
    zip -r "../$ZIP_FILE" . -q
    
    cd ..
    
    # Clean up temp directory
    rm -rf "$TEMP_DIR"
    
    local ZIP_SIZE=$(ls -lah "$ZIP_FILE" | awk '{print $5}')
    print_success "Deployment package created: $ZIP_FILE ($ZIP_SIZE)"
}

create_deployment_bucket() {
    print_info "🪣 Creating S3 deployment bucket..."
    
    # Check if bucket exists
    if aws s3api head-bucket --bucket "$DEPLOYMENT_BUCKET" --profile "$PROFILE" --region "$REGION" 2>/dev/null; then
        print_success "Deployment bucket already exists: $DEPLOYMENT_BUCKET"
        return
    fi
    
    # Create bucket
    if [ "$REGION" = "ap-southeast-1" ]; then
        aws s3api create-bucket \
            --bucket "$DEPLOYMENT_BUCKET" \
            --profile "$PROFILE" \
            --region "$REGION" > /dev/null
    else
        aws s3api create-bucket \
            --bucket "$DEPLOYMENT_BUCKET" \
            --profile "$PROFILE" \
            --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION" > /dev/null
    fi
    
    print_success "Deployment bucket created: $DEPLOYMENT_BUCKET"
}

upload_deployment_package() {
    print_info "⬆️ Uploading deployment package to S3..."
    
    aws s3 cp "$ZIP_FILE" "s3://$DEPLOYMENT_BUCKET/$ZIP_FILE" \
        --profile "$PROFILE" \
        --region "$REGION"
    
    print_success "Deployment package uploaded successfully"
}

deploy_infrastructure() {
    print_info "🏗️ Deploying infrastructure with CloudFormation..."
    
    aws cloudformation deploy \
        --template-file inf/lambda-infrastructure.yaml \
        --stack-name "$STACK_NAME" \
        --parameter-overrides FunctionName="$FUNCTION_NAME" \
        --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
        --profile "$PROFILE" \
        --region "$REGION" \
        --no-fail-on-empty-changeset
    
    print_success "Infrastructure deployed successfully"
}

update_lambda_code() {
    print_info "🔄 Updating Lambda function code..."
    
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --s3-bucket "$DEPLOYMENT_BUCKET" \
        --s3-key "$ZIP_FILE" \
        --profile "$PROFILE" \
        --region "$REGION" > /dev/null
    
    print_success "Lambda function code updated successfully"
}

get_deployment_outputs() {
    print_info "📋 Getting deployment information..."
    
    local OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query "Stacks[0].Outputs" \
        --output json 2>/dev/null || echo "[]")
    
    if [ "$OUTPUTS" != "[]" ]; then
        echo ""
        print_success "🎉 Deployment Complete!"
        echo -e "${GREEN}======================${NC}"
        
        local API_URL=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ApiGatewayUrl") | .OutputValue')
        local CHAT_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ChatEndpoint") | .OutputValue')
        local HEALTH_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="HealthEndpoint") | .OutputValue')
        local FUNCTION_NAME_OUT=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="LambdaFunctionName") | .OutputValue')
        
        echo -e "${CYAN}🌐 API Gateway URL: $API_URL${NC}"
        echo -e "${CYAN}💬 Chat Endpoint: $CHAT_ENDPOINT${NC}"
        echo -e "${CYAN}❤️ Health Check: $HEALTH_ENDPOINT${NC}"
        echo -e "${CYAN}🔧 Function Name: $FUNCTION_NAME_OUT${NC}"
        
        echo ""
        print_info "📖 Test your deployment:"
        echo -e "${CYAN}curl -X POST $CHAT_ENDPOINT \\${NC}"
        echo -e "${CYAN}  -H 'Content-Type: application/json' \\${NC}"
        echo -e "${CYAN}  -d '{\"question\": \"Hello, what can you help me with?\"}'${NC}"
    fi
}

cleanup() {
    rm -f "$ZIP_FILE"
    rm -rf "$TEMP_DIR"
}

# Trap to ensure cleanup on exit
trap cleanup EXIT

# Main deployment process
main() {
    print_header
    
    check_prerequisites
    create_deployment_package
    create_deployment_bucket
    upload_deployment_package
    deploy_infrastructure
    update_lambda_code
    get_deployment_outputs
    
    echo ""
    print_success "🚀 AWS CloudOps Agent deployed successfully!"
}

# Show help if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "AWS CloudOps Agent Lambda Deployment Script"
    echo ""
    echo "USAGE:"
    echo "  $0 [FUNCTION_NAME] [REGION] [PROFILE]"
    echo ""
    echo "PARAMETERS:"
    echo "  FUNCTION_NAME    Name for the Lambda function (default: aws-cloudops-agent)"
    echo "  REGION           AWS region for deployment (default: ap-southeast-1)"
    echo "  PROFILE          AWS CLI profile to use (default: default)"
    echo ""
    echo "EXAMPLES:"
    echo "  # Deploy with default settings"
    echo "  $0"
    echo ""
    echo "  # Deploy with custom function name and region"
    echo "  $0 my-cloudops-agent us-west-2"
    echo ""
    echo "  # Deploy with specific AWS profile"
    echo "  $0 aws-cloudops-agent ap-southeast-1 myprofile"
    echo ""
    echo "REQUIREMENTS:"
    echo "  - AWS CLI configured with appropriate credentials"
    echo "  - Python 3.11+ installed"
    echo "  - jq (for JSON parsing)"
    echo "  - zip utility"
    exit 0
fi

# Run main deployment
main