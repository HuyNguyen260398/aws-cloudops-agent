"""AgentCore Runtime entrypoint: validates the payload and streams the agent's text."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from bedrock_agentcore import BedrockAgentCoreApp
from bedrock_agentcore.runtime import RequestContext

from cloudops_agent.agent import build_agent
from cloudops_agent.config import load_settings
from cloudops_agent.logging_setup import configure_logging

settings = load_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()
# The SDK logger has its own JSON handler (with requestId); don't also emit through ours.
app.logger.propagate = False

INVALID_PROMPT_MSG = "Error: 'prompt' must be a non-empty string."
INTERNAL_ERROR_MSG = "\n[error] The agent hit an internal error. Check the runtime logs."


def _optional_str(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _validate(payload: Any) -> tuple[str | None, str | None]:
    """Return (prompt, error_message); exactly one is set."""
    prompt = payload.get("prompt") if isinstance(payload, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        return None, INVALID_PROMPT_MSG
    if len(prompt) > settings.max_prompt_chars:
        return None, f"Error: prompt exceeds {settings.max_prompt_chars} characters."
    return prompt, None


@app.entrypoint
async def invoke(payload: dict, context: RequestContext) -> AsyncIterator[str]:
    prompt, error = _validate(payload)
    if error:
        yield error
        return

    session_id = _optional_str(context.session_id) or _optional_str(payload.get("session_id"))
    actor_id = _optional_str(payload.get("actor_id")) or "default"

    try:
        agent = build_agent(settings, session_id=session_id, actor_id=actor_id)
        async for event in agent.stream_async(prompt):
            data = event.get("data") if isinstance(event, dict) else None
            if isinstance(data, str) and data:
                yield data
    except Exception:
        logger.exception("Agent invocation failed (session_id=%s)", session_id)
        yield INTERNAL_ERROR_MSG


if __name__ == "__main__":
    app.run(port=8080)
