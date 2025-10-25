import boto3
import json
  
# Initialize the Bedrock AgentCore client
agent_core_client = boto3.client('bedrock-agentcore')
  
# Prepare the payload
payload = json.dumps({"prompt": "hi", "session_id": "asd123", "actor_id": "user"}).encode()
  
# Invoke the agent
response = agent_core_client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:ap-southeast-1:010382427026:runtime/aws_cloudops_agent-t6rEDA5h0K",
    runtimeSessionId="dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt",
    payload=payload
)
  
  
# Process and print the response
if "text/event-stream" in response.get("contentType", ""):
  
    # Handle streaming response
    content = []
    for line in response["response"].iter_lines(chunk_size=10):
        if line:
            line = line.decode("utf-8")
            if line.startswith("data: "):
                line = line[6:]
                print(line)
                content.append(line)
    print("\nComplete response:", "\n".join(content))

elif response.get("contentType") == "application/json":
    # Handle standard JSON response
    content = []
    for chunk in response.get("response", []):
        content.append(chunk.decode('utf-8'))
    print(json.loads(''.join(content)))
  
else:
    # Print raw response for other content types
    print(response)