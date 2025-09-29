# 🚀 AWS CloudOps Agent

A beginner-friendly AWS operations agent built with AWS Strands Agent SDK and  Amazon Bedrock Claude 4 Sonnet.

## ✨ Features

- 📊 **AWS Resource Discovery**: Query your AWS resources and services
- 🏗️ **Architecture Design**: Get architecture recommendations based on your scenarios
- 💡 **Best Practices**: Receive AWS best practices and security recommendations
- 🔍 **Troubleshooting**: Get help with AWS-related issues
- 🧠 **RAG System**: Enhanced responses using DynamoDB-powered knowledge retrieval
- 🎨 **User-Friendly Interface**: Rich console interface with emojis and visual indicators

## 🏛️ Initial Architecture

![AWS CloudOps Agent Architecture](docs/aws-strands-agent.drawio.svg)

## 🛠️ Setup

### Prerequisites

- Python 3.11+
- AWS CLI configured with appropriate credentials
- uv package manager

### Installation

1. Clone or navigate to the project directory:

```bash
cd C:\Workspace\AwsCloudOpsAgent

```

2. Install dependencies:

```bash
uv add strands-agents strands-agents-tools boto3 rich sentence-transformers numpy

```

3. Deploy DynamoDB table:

```bash
cd inf
aws cloudformation deploy --template-file dynamodb-rag.yaml --stack-name aws-cloudops-rag-stack

```

4. Configure AWS credentials:

```bash
aws configure

```

## 🚀 Usage

Run the agent:

```bash
uv run python run_agent.py

```

### Example Interactions

**Resource Discovery:**

```sh
You: Show me my EC2 instances
Agent: 📊 Here are your EC2 instances...

```

**Architecture Design:**

```ini
You: Design a web app architecture for high availability
Agent: 🏗️ For a highly available web application, I recommend...

```

**Best Practices:**

```yaml
You: What's the best way to store user data securely?
Agent: 🔒 For secure user data storage, consider these options...

```

**Knowledge-Enhanced Responses:**

```ini
You: How do I make my EC2 instances highly available?
Agent: 🧠 Based on AWS best practices: Use Auto Scaling Groups...

```

## 🚀 Lambda Deployment

Deploy the AWS CloudOps Agent as a serverless Lambda function with API Gateway for scalable, cost-effective operations.

### Prerequisites for Lambda Deployment

- AWS CLI configured with appropriate permissions
- Python 3.11+ installed
- PowerShell 5.1+ (Windows) or Bash (Unix/Linux/macOS)
- Required AWS permissions:
  - Lambda function management
  - CloudFormation stack operations
  - IAM role creation
  - S3 bucket operations
  - API Gateway management

### Quick Lambda Deployment

```bash
# Windows PowerShell
.\deploy-lambda.ps1

# Unix/Linux/macOS
chmod +x deploy-lambda.sh
./deploy-lambda.sh
```

### Custom Lambda Deployment

```bash
# Deploy with custom function name and region
.\deploy-lambda.ps1 -FunctionName "my-cloudops-agent" -Region "us-west-2"

# Update only the Lambda function code (skip infrastructure)
.\deploy-lambda.ps1 -UpdateCodeOnly

# Unix/Linux equivalent
./deploy-lambda.sh my-cloudops-agent us-west-2 myprofile
```

### Lambda API Usage

After deployment, interact with your agent via HTTP requests:

```bash
# Test the health endpoint
curl https://your-api-gateway-url/prod/health

# Chat with the agent
curl -X POST https://your-api-gateway-url/prod/chat \
  -H 'Content-Type: application/json' \
  -d '{"question": "Show me my EC2 instances"}'
```

### Lambda Features

- **Serverless**: Pay only for what you use, automatic scaling
- **API Gateway**: RESTful API with CORS support
- **Health Checks**: Built-in health monitoring endpoint
- **Session Management**: Optional session tracking for conversations
- **Error Handling**: Comprehensive error responses and logging
- **Security**: IAM-based access control with minimal required permissions

### Lambda Architecture

```
Client Request → API Gateway → Lambda Function → Bedrock Claude 4 → AWS Services
                     ↓
                Health Check
                     ↓
                CloudWatch Logs
```

### Cost Estimation

- **Lambda**: ~$0.20 per 1M requests + $0.0000166667 per GB-second
- **API Gateway**: ~$3.50 per 1M requests
- **Bedrock**: Variable based on model usage
- **CloudWatch**: Minimal logging costs
- **Typical monthly cost**: $5-20 for moderate usage (100-500 requests/month)

## 🔧 Configuration

The agent uses your default AWS CLI profile. To use a different profile:

```python
agent = AwsCloudOpsAgent(aws_profile="your-profile-name")

```

### RAG System

The agent includes a RAG (Retrieval-Augmented Generation) system that:

- Stores AWS knowledge in DynamoDB with semantic embeddings
- Retrieves relevant context for enhanced responses
- Costs <$0.001/month for typical usage
- Auto-populates with AWS best practices

## 📁 Project Structure

```ini
AwsCloudOpsAgent/
├── src/
│   ├── aws_cloudops_agent.py         # Main agent implementation
│   ├── lambda_aws_cloudops_agent.py  # Lambda-optimized agent
│   └── rag_system.py                # RAG system with DynamoDB
├── inf/
│   ├── dynamodb-rag.yaml            # DynamoDB CloudFormation template
│   ├── lambda-infrastructure.yaml    # Lambda CloudFormation template
│   └── deploy.sh                     # DynamoDB deployment script
├── lambda_handler.py                 # Lambda function handler
├── deploy-lambda.ps1                 # Lambda deployment script (Windows)
├── deploy-lambda.sh                  # Lambda deployment script (Unix/Linux)
├── test-lambda.py                    # Lambda deployment test script
├── requirements-lambda.txt           # Lambda-specific dependencies
├── run_agent.py                      # Local entry point
├── requirements.txt                  # Local development dependencies
├── README.md                         # This file
└── pyproject.toml                   # Project configuration

```

## 🤝 Contributing

This is a minimal implementation focused on simplicity and user experience. Feel free to extend with additional features!

## 📝 License

MIT License - feel free to use and modify as needed.