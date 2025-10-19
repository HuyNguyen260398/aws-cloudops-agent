from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from datetime import datetime, timezone
from aws_cloudops_agent import AwsCloudOpsAgent
from strands import Agent
import uuid

app = FastAPI(title="Strands Agent Server", version="1.0.0")
agent_sessions: Dict[str, Agent] = {}


class InvocationRequest(BaseModel):
    input: Dict[str, Any]
    session_id: str = None


class InvocationResponse(BaseModel):
    output: Dict[str, Any]
    session_id: str = None


class PromptRequest(BaseModel):
    prompt: str
    session_id: str = None


def get_or_create_agent(session_id: str = None) -> tuple[Agent, str]:
    """Get existing agent or create new one."""
    if session_id and session_id in agent_sessions:
        return agent_sessions[session_id], session_id

    # Create new agent
    new_session_id = str(uuid.uuid4())
    agent = AwsCloudOpsAgent()
    agent_sessions[new_session_id] = agent
    return agent, new_session_id


@app.post("/invocations", response_model=InvocationResponse)
async def invoke_agent(request: InvocationRequest):
    try:
        agent, session_id = get_or_create_agent(request.session_id)
        user_message = request.input.get("prompt", "")

        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No prompt found in input. Please provide a 'prompt' key in the input.",
            )

        # Collect all chunks from the async generator
        result_chunks = []
        async for chunk in agent.stream(user_message):
            result_chunks.append(chunk)

        # Join all chunks into a single message
        result = "".join(result_chunks)

        response = {"message": result}

        return InvocationResponse(output=response, session_id=session_id)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Agent processing failed: {str(e)}"
        )


@app.post("/stream")
async def stream_response(request: PromptRequest):
    async def generate():
        try:
            agent, session_id = get_or_create_agent(request.session_id)
            async for chunk in agent.stream(request.prompt):
                yield chunk
        except Exception as e:
            yield f"Error: {str(e)}"

    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/ping")
async def ping():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
