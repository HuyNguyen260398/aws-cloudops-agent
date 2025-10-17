from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from aws_cloudops_agent import AwsCloudOpsAgent

console = Console()


def display_welcome():
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


def display_response(response: str):
    final_response = ""
    # Extract text content from the message
    if hasattr(response, "message") and "content" in response.message:
        content_blocks = response.message["content"]
        if content_blocks and isinstance(content_blocks, list):
            final_response = content_blocks[0].get("text", str(response))

    final_response = final_response if final_response else str(response)
    """Display agent response with formatting"""
    console.print(
        Panel(final_response, title="🤖 AWS CloudOps Agent", border_style="green")
    )


def main():
    """Main interactive loop"""
    agent = AwsCloudOpsAgent()
    display_welcome()

    console.print(
        "\n[bold yellow]💡 Tip: Type 'quit' or 'exit' to end the session[/bold yellow]\n"
    )

    while True:
        try:
            # Get user input
            user_input = console.input("\n[bold cyan]You:[/bold cyan] ")

            if user_input.lower() in ["quit", "exit", "bye"]:
                console.print(
                    "\n👋 Thanks for using AWS CloudOps Agent! Have a great day!"
                )
                break

            if not user_input.strip():
                continue

            # Get and display response
            response = agent.chat(user_input)
            display_response(response)

        except KeyboardInterrupt:
            console.print("\n\n👋 Thanks for using AWS CloudOps Agent!")
            break
        except Exception as e:
            console.print(f"\n❌ Error: {str(e)}")


if __name__ == "__main__":
    main()
