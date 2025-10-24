import boto3
import json

client = boto3.client("bedrock-agentcore", region_name="ap-southeast-1")
payload = json.dumps(
    {
        "input": {
            "prompt": "hi",
        },
        "session_id": "6af56d21-5767-42d8-8faf-452a0f643aac"
    }
)

response = client.invoke_agent_runtime(
    agentRuntimeArn="",
    runtimeSessionId="",  # Must be 33+ chars
    payload=payload,
    qualifier="DEFAULT",  # Optional
)
response_body = response["response"].read()
response_data = json.loads(response_body)
print("Agent Response:")
print(json.dumps(response_data, indent=2, ensure_ascii=False))
