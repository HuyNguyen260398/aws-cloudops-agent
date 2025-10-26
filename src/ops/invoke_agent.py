import boto3
import json
import os
import sys
import uuid
import threading
import time

# Add project root and src to path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
src_path = os.path.join(project_root, "src")
sys.path.append(project_root)
sys.path.append(src_path)

from utils.responses import print_agentcore_response_sync
from utils.config_manager import AgentCoreConfigManager

# Initialize configuration
config_manager = AgentCoreConfigManager()
merged_config = config_manager.get_merged_config()

# Get runtime ARN from config
runtime_arn = merged_config['runtime']['p_agent']['arn']

if not runtime_arn:
    print("❌ Runtime ARN not found in config. Please deploy the runtime first.")
    sys.exit(1)

# Initialize the Bedrock AgentCore client
agent_core_client = boto3.client("bedrock-agentcore")

# Generate session ID for the conversation
session_id = str(uuid.uuid4())

print("\n🤖 AWS CloudOps Agent - Chat Mode")
print("Type 'exit', 'end', or 'bye' to quit\n")
print("=" * 50)

# Chat loop
while True:
    # Get user input
    user_prompt = input("\n💬 You: ").strip()
    
    if not user_prompt:
        continue
    
    # Check for exit commands
    if user_prompt.lower() in ['exit', 'end', 'bye']:
        print("\n👋 Goodbye!")
        break
    
    # Prepare the payload
    payload = json.dumps(
        {"prompt": user_prompt, "session_id": session_id, "actor_id": "user"}
    ).encode()
    
    # Loading animation
    loading = True
    def show_loading():
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        idx = 0
        while loading:
            print(f"\r🤖 Agent: {spinner[idx % len(spinner)]}", end="", flush=True)
            idx += 1
            time.sleep(0.1)
    
    loader = threading.Thread(target=show_loading, daemon=True)
    loader.start()
    
    # Invoke the agent
    response = agent_core_client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        payload=payload,
    )
    
    # Stop loading and clear line
    loading = False
    time.sleep(0.15)
    print("\r🤖 Agent: ", end="", flush=True)
    
    # Print response with lazy loading (streaming)
    print_agentcore_response_sync(response)
    print("\n" + "=" * 50)


