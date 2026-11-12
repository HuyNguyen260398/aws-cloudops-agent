"""Typed runtime settings, read from environment variables."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

# Newest Claude Sonnet-class global inference profile listed in ap-southeast-1 on 2026-11-12.
# Keep in sync with the `model_id` default in infra/variables.tf.
DEFAULT_MODEL_ID = "global.anthropic.claude-sonnet-5-5"
DEFAULT_REGION = "ap-southeast-1"


@dataclass(frozen=True)
class Settings:
    model_id: str
    region: str
    memory_id: str | None
    log_level: str
    max_prompt_chars: int
    max_tool_output_chars: int


def _get(env: Mapping[str, str], name: str) -> str | None:
    value = env.get(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def _get_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = _get(env, name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from `env` (defaults to os.environ)."""
    if env is None:
        env = os.environ
    return Settings(
        model_id=_get(env, "MODEL_ID") or DEFAULT_MODEL_ID,
        region=_get(env, "AWS_REGION") or _get(env, "AWS_DEFAULT_REGION") or DEFAULT_REGION,
        memory_id=_get(env, "MEMORY_ID"),
        log_level=(_get(env, "LOG_LEVEL") or "INFO").upper(),
        max_prompt_chars=_get_int(env, "MAX_PROMPT_CHARS", 10000),
        max_tool_output_chars=_get_int(env, "MAX_TOOL_OUTPUT_CHARS", 20000),
    )
