from strands import Agent
from strands.models import BedrockModel
from strands_tools import use_aws


class AwsCloudOpsAgent:
    def __init__(self):

        # Initialize Bedrock model with Claude 4 Sonnet
        self.model = BedrockModel(
            model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0",
        )

        # Initialize the agent with AWS tools
        self.agent = Agent(
            model=self.model,
            tools=[use_aws],
            system_prompt=self._get_system_prompt(),
        )

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent"""
        return """
        You are an AWS CloudOps Agent, a friendly and knowledgeable assistant specializing in AWS cloud operations.
        
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
        """
    
    def chat(self, message: str):
        """Process user message and return response"""
        try:
            result = self.agent(message)
            return result
            
        except Exception as e:
            return f"Sorry, I encountered an error: {str(e)}"
        
    async def stream(self, message: str):
        """Process user message and return response"""
        try:
            async for event in self.agent.stream_async(message):
                if "data" in event:
                    # Only stream text chunks to the client
                    yield event["data"]

        except Exception as e:
            yield f"Sorry, I encountered an error: {str(e)}"


def main():
    """Main interactive loop"""
    agent = AwsCloudOpsAgent()


if __name__ == "__main__":
    main()
