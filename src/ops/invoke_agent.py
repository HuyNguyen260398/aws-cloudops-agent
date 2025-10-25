import boto3
import json

client = boto3.client("bedrock-agentcore", region_name="ap-southeast-1")
payload = json.dumps(
    {"prompt": "hi", "session_id": "asd123", "actor_id": "user"}
)

response = client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:ap-southeast-1:010382427026:runtime/aws_cloudops_agent-t6rEDA5h0K",
    runtimeSessionId="dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt",  # Must be 33+ chars
    payload=payload,
    qualifier="DEFAULT",  # Optional
)
response_body = response["response"].read()
# response_data = json.loads(response_body)
print("Agent Response:", response_body)
