"""
AWS Lambda-optimized CloudOps Agent
Simplified version without rich console for better Lambda performance
"""
import re
from typing import Dict, Any, List
from strands import Agent
from strands.models import BedrockModel
from strands_tools import use_aws

class LambdaAwsCloudOpsAgent:
    def __init__(self, aws_profile: str = "default"):
        """Initialize the AWS CloudOps Agent for Lambda"""
        self.aws_profile = aws_profile
        
        # Initialize Bedrock model with Claude 4 Sonnet
        self.model = BedrockModel(
            model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0",
            # aws_profile=aws_profile  # Lambda uses instance role
        )
        
        # Initialize the agent with AWS tools
        self.agent = Agent(
            model=self.model,
            tools=[use_aws],
            system_prompt=self._get_system_prompt()
        )
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent"""
        return """
        You are an AWS CloudOps Agent 🚀, a friendly and knowledgeable assistant specializing in AWS cloud operations.
        
        Your capabilities:
        - 📊 Retrieve information about AWS services and resources
        - 🏗️ Provide architecture solutions based on user scenarios
        - 💡 Offer best practices and recommendations
        - 🔍 Help troubleshoot AWS-related issues
        
        Guidelines:
        - Use emojis and visual indicators to make responses engaging
        - Provide clear, concise explanations suitable for beginners
        - When suggesting architectures, explain the reasoning behind service choices
        - Always consider cost-effectiveness and security best practices
        - Use the use_aws tool to interact with AWS services when needed
        
        Response format:
        - Start with a relevant emoji
        - Use bullet points for clarity
        - Include practical examples when possible
        - End with helpful next steps or recommendations
        
        You are running in AWS Lambda, so responses should be optimized for API consumption.
        """

    def chat(self, message: str) -> str:
        """Process user message and return response"""
        try:
            result = self.agent(message)
            
            # Extract text content from the message
            if hasattr(result, 'message') and 'content' in result.message:
                content_blocks = result.message['content']
                if content_blocks and isinstance(content_blocks, list):
                    return content_blocks[0].get('text', str(result))
            
            return str(result)
            
        except Exception as e:
            return f"❌ Sorry, I encountered an error: {str(e)}"