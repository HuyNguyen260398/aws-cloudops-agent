import boto3
import json

client = boto3.client('bedrock-agentcore', region_name='ap-southeast-2')
payload = json.dumps({
    "input": {"prompt": "Are there any S3 buckets in my AWS account in ap-southeast-2 that is created for testing purposes?"}
})

response = client.invoke_agent_runtime(
    agentRuntimeArn="arn:aws:bedrock-agentcore:ap-southeast-2:010382427026:runtime/aws_cloudops_agent-J5YIRnCKjD",
    runtimeSessionId="dfmeoagmreaklgmrkleafremoigrmtesogmtrskhmtkrlshmt",  # Must be 33+ chars
    payload=payload,
    qualifier="DEFAULT",  # Optional
)

response_body = response['response'].read()
response_data = json.loads(response_body)
print("Agent Response:")
print(json.dumps(response_data, indent=2))
