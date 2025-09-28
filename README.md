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
│   ├── aws_cloudops_agent.py    # Main agent implementation
│   └── rag_system.py           # RAG system with DynamoDB
├── inf/
│   ├── dynamodb-rag.yaml       # CloudFormation template
│   └── deploy.sh               # Deployment script
├── run_agent.py                 # Entry point
├── requirements.txt             # Dependencies
├── README.md                    # This file
└── pyproject.toml              # Project configuration
```

## 🤝 Contributing

This is a minimal implementation focused on simplicity and user experience. Feel free to extend with additional features!

## 📝 License

MIT License - feel free to use and modify as needed.