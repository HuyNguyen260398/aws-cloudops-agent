import functools
import sys
import os
import time
from datetime import datetime
from typing import AsyncGenerator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Add project root to path
project_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.append(project_root)

# AWS documented imports
from mcp.client.streamable_http import streamablehttp_client
from strands import tool
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient, MCPAgentTool
from strands_tools import use_aws, handoff_to_user

# Shared utilities
from agents.aws_cloudops_agent import AwsCloudOpsAgent
from utils.config_manager import AgentCoreConfigManager
from utils.query_extractor import extract_tool_query
from components.gateway import tool_search

from utils.responses import (
    format_diy_response,
    extract_text_from_event,
    format_error_response,
)

from components.auth import (
    is_oauth_available,
    setup_oauth,
    get_m2m_token,
)

from components.memory import (
    setup_memory,
    get_conversation_context,
    save_conversation,
    is_memory_available,
)

import utils.mylogger as mylogger

logger = mylogger.get_logger()


# ============================================================================
# EXACT AWS DOCUMENTATION PATTERNS
# ============================================================================


def _create_streamable_http_transport(url, headers=None):
    """
    EXACT function from AWS documentation
    https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-using-mcp-clients.html
    """
    return streamablehttp_client(url, headers=headers)


async def execute_agent_streaming(bedrock_model, prompt, pending_confirmation=None):
    """
    Streaming version of AWS documented pattern with handoff support
    """
    # Get configuration
    config_manager = AgentCoreConfigManager()
    gateway_url = config_manager.get_gateway_url()

    # Fallback to local tools if gateway or oauth is not working
    if not gateway_url or not is_oauth_available():
        logger.info("🏠 No MCP available - using local streaming")
        local_tools = [get_current_time, echo_message, use_aws, handoff_to_user]
        agent = AwsCloudOpsAgent(model=bedrock_model, tools=local_tools)
        handoff_detected = False
        async for event in agent.stream_async(prompt):
            # Check for handoff_to_user tool usage
            if _is_handoff_event(event):
                yield {"handoff_required": True, "event": event}
                handoff_detected = True
            elif not handoff_detected:
                yield event
        return

    try:
        access_token = get_m2m_token()
        if not access_token:
            raise Exception("No access token")

        # Create headers for authentication
        headers = {"Authorization": f"Bearer {access_token}"}

        # EXACT AWS pattern: Create MCP client with functools.partial
        mcp_client = MCPClient(
            functools.partial(
                _create_streamable_http_transport, url=gateway_url, headers=headers
            )
        )

        # EXACT AWS pattern: Use context manager
        with mcp_client:
            # Use semantic search to get relevant tools
            search_query = extract_tool_query(prompt)
            logger.info(f"🔍 Tool search query: {search_query}")
            
            searched_tools = tool_search(gateway_url, access_token, search_query)
            logger.info(f"🎯 Found {len(searched_tools)} relevant tools")
            
            # Convert to MCPAgentTool format
            from mcp.types import Tool as MCPTool
            tools = []
            for tool in searched_tools[:10]:  # Limit to top 10
                mcp_tool = MCPTool(
                    name=tool["name"],
                    description=tool["description"],
                    inputSchema=tool["inputSchema"],
                )
                tools.append(MCPAgentTool(mcp_tool, mcp_client))

            # Add local tools
            all_tools = [get_current_time, echo_message, use_aws, handoff_to_user]
            if tools:
                all_tools.extend(tools)
                logger.info(f"🛠️ Streaming with {len(tools)} searched MCP tools + local tools")

            logger.info(f"🛠️ Total tools available: {len(all_tools)} (searched: {len(tools)}, local: 4)")

            agent = AwsCloudOpsAgent(model=bedrock_model, tools=all_tools)
            handoff_detected = False
            async for event in agent.stream_async(prompt):
                # Check for handoff_to_user tool usage
                if _is_handoff_event(event):
                    yield {"handoff_required": True, "event": event}
                    handoff_detected = True
                elif not handoff_detected:
                    yield event

    except Exception as e:
        logger.error(f"❌ MCP streaming failed: {e}")
        # Fallback to local streaming
        logger.info("🏠 Falling back to local streaming")
        local_tools = [get_current_time, echo_message, use_aws, handoff_to_user]
        agent = AwsCloudOpsAgent(model=bedrock_model, tools=local_tools)
        handoff_detected = False
        async for event in agent.stream_async(prompt):
            if _is_handoff_event(event):
                yield {"handoff_required": True, "event": event}
                handoff_detected = True
            elif not handoff_detected:
                yield event


# ============================================================================
# HANDOFF DETECTION
# ============================================================================


def _is_handoff_event(event) -> bool:
    """Check if event contains handoff_to_user tool usage or confirmation prompt"""
    if not isinstance(event, dict):
        return False
    
    # Check for tool use in event structure
    if "event" in event:
        inner = event["event"]
        if "contentBlockStart" in inner:
            start = inner["contentBlockStart"].get("start", {})
            if "toolUse" in start:
                return start["toolUse"].get("name") == "handoff_to_user"
        
        # Check for confirmation prompt in text content
        if "contentBlockDelta" in inner:
            delta = inner["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                text = delta["text"]
                if "Do you want to proceed? [y/*]" in text or "is potentially mutative" in text:
                    return True
    
    return False


# ============================================================================
# LOCAL TOOLS
# ============================================================================


@tool(name="get_current_time", description="Get the current date and time")
def get_current_time() -> str:
    """Get current timestamp"""
    from datetime import datetime

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")


@tool(name="echo_message", description="Echo back a message for testing")
def echo_message(message: str) -> str:
    """Echo back the provided message"""
    return f"Echo: {message}"


# ============================================================================
# CONFIGURATION
# ============================================================================


config_manager = AgentCoreConfigManager()
model_settings = config_manager.get_model_settings()
logger.info(f"🚀 AWS CloudOps Agent with Bedrock model: {model_settings['model_id']}")


# ============================================================================
# STREAMING RESPONSE
# ============================================================================


async def stream_response(
    user_message: str, session_id: str = None, actor_id: str = "user"
) -> AsyncGenerator[str, None]:
    """Stream agent response using AWS documented patterns"""
    response_parts = []

    try:
        logger.info(f"🔄 Processing: {user_message[:50]}...")

        # Get conversation context if available
        context = ""
        if is_memory_available() and session_id:
            context = get_conversation_context(session_id, actor_id)

        # Prepare message with context
        final_message = user_message
        if context:
            final_message = f"{context}\n\nCurrent user message: {user_message}"

        # Create model with longer timeout for streaming
        model = BedrockModel(**model_settings, streaming=True)

        # Use AWS documented streaming pattern
        last_event_time = time.time()

        handoff_detected = False
        async for event in execute_agent_streaming(model, final_message):
            # Check for handoff requirement
            if isinstance(event, dict) and event.get("handoff_required"):
                logger.info("🤚 Handoff to user required - pausing execution")
                yield "data: {\"type\": \"handoff_required\", \"message\": \"Agent requires your confirmation to proceed. Please respond with 'yes' or 'no'.\"}\n\n"
                handoff_detected = True
                continue
            
            # Skip remaining events after handoff
            if handoff_detected:
                continue
            
            # Format and yield response
            formatted = format_diy_response(event)
            yield formatted
            last_event_time = time.time()

            # Collect text for memory
            text = extract_text_from_event(event)
            if text:
                response_parts.append(text)

        # Save to memory if available
        if is_memory_available() and session_id and response_parts:
            full_response = "".join(response_parts)
            save_conversation(session_id, user_message, full_response, actor_id)
            logger.info("💾 Conversation saved")

    except Exception as e:
        logger.error(f"❌ Streaming error: {e}")
        error_response = format_error_response(str(e), "agent_runtime")
        yield error_response


# ============================================================================
# INITIALIZATION
# ============================================================================


def initialize():
    """Initialize OAuth and Memory"""
    logger.info("🚀 Initializing AWS CloudOps Agent...")

    if setup_oauth():
        logger.info("✅ OAuth initialized")
    else:
        logger.warning("⚠️ OAuth not available")

    if setup_memory():
        logger.info("✅ Memory initialized")
    else:
        logger.warning("⚠️ Memory not available")

    logger.info("✅ AWS CloudOps Agent ready")


# Initialize on startup
try:
    initialize()
except Exception as e:
    logger.error(f"❌ Initialization failed: {e}")


# ============================================================================
# FASTAPI APP
# ============================================================================


app = FastAPI(title="AWS CloudOps Agent", version="1.0.0")


class InvocationRequest(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    actor_id: str = "user"


@app.post("/invocations")
async def invoke_agent(request: InvocationRequest):
    """AgentCore Runtime endpoint using exact AWS MCP patterns"""
    logger.info("📥 Received invocation request")

    try:
        return StreamingResponse(
            stream_response(request.prompt, request.session_id, request.actor_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",  # ,
                # "X-Accel-Buffering": "no",  # Disable nginx buffering
                # "Transfer-Encoding": "chunked"
            },
        )

    except Exception as e:
        logger.error(f"💥 Request failed: {e}")
        raise HTTPException(
            status_code=500, detail=f"Agent processing failed: {str(e)}"
        )


@app.get("/ping")
async def ping():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "time_of_last_update": datetime.now().strftime("%Y%m%d-%H%M%S"),
    }


# ============================================================================
# MAIN
# ============================================================================


if __name__ == "__main__":
    logger.info("🚀 Starting AWS CloudOps Agent ...")
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)