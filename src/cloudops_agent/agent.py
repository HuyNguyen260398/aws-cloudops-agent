"""Agent factory: model, tools, prompt, conversation manager, and optional memory."""

from __future__ import annotations

from datetime import UTC, datetime

from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from strands import Agent
from strands.agent.conversation_manager import SummarizingConversationManager
from strands.models import BedrockModel
from strands.vended_plugins.context_injector import ContextInjector

from cloudops_agent.config import Settings
from cloudops_agent.prompts import SYSTEM_PROMPT
from cloudops_agent.tools import make_aws_read_tool


def _current_time(*_args: object, **_kwargs: object) -> str:
    return f"Current UTC time: {datetime.now(UTC).isoformat(timespec='seconds')}"


def build_agent(settings: Settings, session_id: str | None, actor_id: str = "default") -> Agent:
    """Build a fresh agent. Memory is enabled only with both a memory ID and a session ID."""
    session_manager = None
    if settings.memory_id and session_id:
        session_manager = AgentCoreMemorySessionManager(
            AgentCoreMemoryConfig(
                memory_id=settings.memory_id, session_id=session_id, actor_id=actor_id
            ),
            region_name=settings.region,
        )

    return Agent(
        model=BedrockModel(model_id=settings.model_id, region_name=settings.region, streaming=True),
        system_prompt=SYSTEM_PROMPT,
        tools=[make_aws_read_tool(settings)],
        conversation_manager=SummarizingConversationManager(
            summary_ratio=0.3, preserve_recent_messages=10
        ),
        plugins=[ContextInjector(_current_time, name="current_time")],
        session_manager=session_manager,
        callback_handler=None,  # nothing printed to stdout; the entrypoint streams events
    )
