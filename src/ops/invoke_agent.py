import boto3
import json
import os
import sys

# Add project root and src to path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
src_path = os.path.join(project_root, "src")
sys.path.append(project_root)
sys.path.append(src_path)

from utils.responses import extract_agent_message_from_response


# Initialize the Bedrock AgentCore client
agent_core_client = boto3.client("bedrock-agentcore")

# Prepare the payload
payload = json.dumps(
    {"prompt": "hi", "session_id": "asd123", "actor_id": "user"}
).encode()

# Invoke the agent
response = agent_core_client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:ap-southeast-1:010382427026:runtime/aws_cloudops_agent-t6rEDA5h0K",
    runtimeSessionId="dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt",
    payload=payload,
)

# Option 1: Extract only the agent message
print("=== AGENT MESSAGE ONLY ===")
agent_message = extract_agent_message_from_response(response)
print(agent_message)
print("=" * 50)

# Option 2: Show raw response (commented out by default)
# print("\n=== RAW RESPONSE ===")
# # Process and print the response
# if "text/event-stream" in response.get("contentType", ""):
#     # Handle streaming response
#     content = []
#     for line in response["response"].iter_lines(chunk_size=10):
#         if line:
#             line = line.decode("utf-8")
#             if line.startswith("data: "):
#                 line = line[6:]
#                 print(line)
#                 content.append(line)
#     print("\nComplete response:", "\n".join(content))

# elif response.get("contentType") == "application/json":
#     # Handle standard JSON response
#     content = []
#     for chunk in response.get("response", []):
#         content.append(chunk.decode('utf-8'))
#     print(json.loads(''.join(content)))

# else:
#     # Print raw response for other content types
#     print(response)
