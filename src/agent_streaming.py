from aws_cloudops_agent import AwsCloudOpsAgent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

app = BedrockAgentCoreApp()
agent = AwsCloudOpsAgent()


@app.entrypoint
async def strands_agent_bedrock_streaming(payload):
    """
    Invoke the agent with streaming capabilities
    This function demonstrates how to implement streaming responses
    with AgentCore Runtime using async generators
    """
    user_input = payload.get("prompt")
    print("User input:", user_input)

    try:
        # Stream each chunk as it becomes available
        async for event in agent.stream_async(user_input):
            if "data" in event:
                yield event["data"]

    except Exception as e:
        # Handle errors gracefully in streaming context
        error_response = {"error": str(e), "type": "stream_error"}
        print(f"Streaming error: {error_response}")
        yield error_response


if __name__ == "__main__":
    app.run()
