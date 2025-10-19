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


class ChatRequest(BaseModel):
    prompt: str
    session_id: str = None


class ChatResponse(BaseModel):
    response: Dict[str, Any]
    session_id: str


def get_or_create_agent(session_id: str = None) -> tuple[Agent, str]:
    """Get existing agent or create new one."""
    if session_id and session_id in agent_sessions:
        return agent_sessions[session_id], session_id

    # Create new agent
    new_session_id = str(uuid.uuid4())
    agent = AwsCloudOpsAgent()
    agent_sessions[new_session_id] = agent
    return agent, new_session_id


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        agent, session_id = get_or_create_agent(request.session_id)

        user_message = request.prompt
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No prompt provided. Please provide a prompt.",
            )

        # Collect all chunks from the async generator
        result_chunks = []
        async for chunk in agent.stream(user_message):
            result_chunks.append(chunk)

        # Join all chunks into a single message
        result = "".join(result_chunks)

        response = {"message": result}

        return ChatResponse(response=response, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a specific session."""
    if session_id in agent_sessions:
        del agent_sessions[session_id]
        return {"message": "Session cleared"}
    raise HTTPException(status_code=404, detail="Session not found")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
