# 🚀 AWS CloudOps Agent

A beginner-friendly AWS operations agent built with AWS Strands Agent SDK and  Amazon Bedrock Claude 4 Sonnet.

## ✨ Features

- 📊 **AWS Resource Discovery**: Query your AWS resources and services
- 🏗️ **Architecture Design**: Get architecture recommendations based on your scenarios
- 💡 **Best Practices**: Receive AWS best practices and security recommendations
- 🔍 **Troubleshooting**: Get help with AWS-related issues
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
uv add strands-agents strands-agents-tools boto3 rich
```

3. Configure AWS credentials:

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

## 🔧 Configuration

The agent uses your default AWS CLI profile. To use a different profile:

```python
agent = AwsCloudOpsAgent(aws_profile="your-profile-name")

```

## 📁 Project Structure

```ini
AwsCloudOpsAgent/
├── src/
│   └── aws_cloudops_agent.py           # Main agent implementation
├── docs/
│   ├── AWS-CloudOps-Agent.pptx         # Presentation
│   ├── aws-strands-agent.drawio        # Architecture diagram
│   ├── aws-strands-agent.drawio.svg    # Architecture diagram (SVG)
│   └── ROADMAP.md                      # Project roadmap
├── main.py                             # Alternative entry point
├── run_agent.py                        # Primary entry point
├── requirements.txt                    # Dependencies
├── pyproject.toml                      # Project configuration
├── uv.lock                             # Dependency lock file
└── README.md                           # This file
```

## 🤝 Contributing

This is a minimal implementation focused on simplicity and user experience. Feel free to extend with additional features!

## 📝 License

MIT License - feel free to use and modify as needed.