"""
AWS CloudOps Agent - A beginner-friendly agent for AWS operations
"""
import asyncio
import re
from typing import Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from strands import Agent
from strands.models import BedrockModel
from strands_tools import use_aws

console = Console()

class AwsCloudOpsAgent:
    def __init__(self, aws_profile: str = "default"):
        """Initialize the AWS CloudOps Agent"""
        self.aws_profile = aws_profile
        
        # Initialize Bedrock model with Claude 4 Sonnet
        self.model = BedrockModel(
            model_id="apac.anthropic.claude-sonnet-4-20250514-v1:0",
            aws_profile=aws_profile
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
        """
    
    async def chat(self, message: str) -> str:
        """Process user message and return response"""
        try:
            # Show thinking indicator
            with console.status("[bold green]🤔 Thinking about your AWS question..."):
                response = await self.agent(message)
            
            return response
            
        except Exception as e:
            return f"❌ Sorry, I encountered an error: {str(e)}"
    
    def display_welcome(self):
        """Display welcome message"""
        welcome_text = Text()
        welcome_text.append("🚀 AWS CloudOps Agent", style="bold blue")
        welcome_text.append("\n\nI'm here to help you with AWS cloud operations!")
        welcome_text.append("\n\n✨ What I can do:")
        welcome_text.append("\n• 📊 Check your AWS resources and services")
        welcome_text.append("\n• 🏗️ Design cloud architectures for your needs")
        welcome_text.append("\n• 💡 Provide AWS best practices and recommendations")
        welcome_text.append("\n• 🔍 Help troubleshoot AWS issues")
        welcome_text.append("\n\n💬 Try asking me:")
        welcome_text.append("\n• 'Show me my EC2 instances'")
        welcome_text.append("\n• 'Design a web app architecture for high availability'")
        welcome_text.append("\n• 'What's the best way to store user data securely?'")
        
        console.print(Panel(welcome_text, title="Welcome", border_style="blue"))
    
    def display_response(self, response: str):
        """Display agent response with formatting"""
        console.print(Panel(response, title="🤖 AWS CloudOps Agent", border_style="green"))

async def main():
    """Main interactive loop"""
    agent = AwsCloudOpsAgent()
    agent.display_welcome()
    
    console.print("\n[bold yellow]💡 Tip: Type 'quit' or 'exit' to end the session[/bold yellow]\n")
    
    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ")
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                console.print("\n👋 Thanks for using AWS CloudOps Agent! Have a great day!")
                break
            
            if not user_input.strip():
                continue
            
            # Get and display response
            response = await agent.chat(user_input)
            agent.display_response(response)
            
        except KeyboardInterrupt:
            console.print("\n\n👋 Thanks for using AWS CloudOps Agent!")
            break
        except Exception as e:
            console.print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())