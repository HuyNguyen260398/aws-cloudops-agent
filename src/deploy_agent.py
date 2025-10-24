import boto3
import os

# Get environment variables from system
aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION", "ap-southeast-1")  # Default to ap-southeast-1

# Validate required environment variables
if not aws_access_key or not aws_secret_key:
    raise ValueError(
        "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables are required"
    )

client = boto3.client("bedrock-agentcore-control", region_name=aws_region)

# Environment variables to pass to the container
environment_variables = {
    "AWS_ACCESS_KEY_ID": aws_access_key,
    "AWS_SECRET_ACCESS_KEY": aws_secret_key,
    "AWS_REGION": aws_region,
    "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    "DEBUG": os.getenv("DEBUG", "false"),
    "PYTHONPATH": "/app",
}

response = client.update_agent_runtime(
    # agentRuntimeName="aws_cloudops_agent",
    agentRuntimeId="",
    agentRuntimeArtifact={
        "containerConfiguration": {
            "containerUri": ""
        }
    },
    networkConfiguration={"networkMode": "PUBLIC"},
    roleArn="arn:aws:iam::010382427026:role/AgentRuntimeRole",
    environmentVariables={
        "AWS_ACCESS_KEY_ID": aws_access_key,
        "AWS_SECRET_ACCESS_KEY": aws_secret_key,
        "AWS_REGION": aws_region,
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
        "DEBUG": os.getenv("DEBUG", "false"),
        "PYTHONPATH": "/app",
    },
)

print(f"Agent Runtime created successfully!")
print(f"Agent Runtime ARN: {response['agentRuntimeArn']}")
print(f"Status: {response['status']}")
