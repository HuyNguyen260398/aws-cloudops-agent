"""
AWS CloudOps Agent - Minimal Lambda version
Serverless-friendly version without heavy ML dependencies
"""
import logging
from strands import Agent
from strands.models import BedrockModel
from strands_tools import use_aws

# Configure logging
logger = logging.getLogger(__name__)

class MinimalLambdaAwsCloudOpsAgent:
    def __init__(self, aws_profile: str = "default"):
        """Initialize the AWS CloudOps Agent for Lambda (minimal version)"""
        self.aws_profile = aws_profile
        
        # Initialize Bedrock model with Claude 4 Sonnet
        self.model = BedrockModel(
            model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0",
            # aws_profile=aws_profile
        )
        
        # Initialize the agent with AWS tools
        self.agent = Agent(
            model=self.model,
            tools=[use_aws],
            system_prompt=self._get_system_prompt()
        )
        
        logger.info("Minimal AWS CloudOps Agent initialized for Lambda")
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent"""
        return """
        You are an AWS CloudOps Agent, a knowledgeable assistant specializing in AWS cloud operations.
        
        Your capabilities:
        - Retrieve information about AWS services and resources
        - Provide architecture solutions based on user scenarios
        - Offer best practices and recommendations
        - Help troubleshoot AWS-related issues
        
        Guidelines:
        - Provide clear, concise explanations suitable for beginners
        - When suggesting architectures, explain the reasoning behind service choices
        - Always consider cost-effectiveness and security best practices
        - Use the use_aws tool to interact with AWS services when needed
        
        Response format:
        - Use bullet points for clarity
        - Include practical examples when possible
        - End with helpful next steps or recommendations
        
        Note: You are running in a serverless environment optimized for basic AWS operations.
        For advanced analytics or complex data processing, recommend appropriate AWS services.
        """

    def chat(self, message: str) -> str:
        """Process user message and return response"""
        try:
            logger.info(f"Processing message: {message[:100]}...")
            result = self.agent(message)
            
            # Extract text content from the message
            if hasattr(result, 'message') and 'content' in result.message:
                content_blocks = result.message['content']
                if content_blocks and isinstance(content_blocks, list):
                    response = content_blocks[0].get('text', str(result))
                else:
                    response = str(result)
            else:
                response = str(result)
            
            logger.info("Successfully generated response")
            return response
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            logger.error(f"Error in chat: {str(e)}")
            return error_msg