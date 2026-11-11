from unittest.mock import MagicMock

import pytest

from cloudops_agent import agent as agent_module
from cloudops_agent.agent import build_agent
from cloudops_agent.config import load_settings
from cloudops_agent.prompts import SYSTEM_PROMPT


@pytest.fixture
def session_manager_cls(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "ap-southeast-1")
    mock = MagicMock()
    monkeypatch.setattr(agent_module, "AgentCoreMemorySessionManager", mock)
    return mock


def test_agent_has_only_aws_read_tool(session_manager_cls):
    assert build_agent(load_settings({}), None).tool_names == ["aws_read"]


def test_agent_uses_settings_model_and_prompt(session_manager_cls):
    agent = build_agent(load_settings({"MODEL_ID": "my-model"}), None)
    assert agent.model.config["model_id"] == "my-model"
    assert agent.system_prompt == SYSTEM_PROMPT


def test_no_memory_without_memory_id(session_manager_cls):
    build_agent(load_settings({}), "s" * 33)
    session_manager_cls.assert_not_called()


def test_no_memory_without_session_id(session_manager_cls):
    build_agent(load_settings({"MEMORY_ID": "mem-1"}), None)
    session_manager_cls.assert_not_called()


def test_memory_enabled(session_manager_cls):
    build_agent(load_settings({"MEMORY_ID": "mem-1"}), "s" * 33, actor_id="u1")
    session_manager_cls.assert_called_once()
    config = session_manager_cls.call_args.args[0]
    assert (config.memory_id, config.session_id, config.actor_id) == ("mem-1", "s" * 33, "u1")
    assert session_manager_cls.call_args.kwargs["region_name"] == "ap-southeast-1"


def test_prompt_states_read_only():
    assert "read-only" in SYSTEM_PROMPT.lower()
