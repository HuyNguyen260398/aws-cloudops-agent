import json
import logging
from unittest.mock import MagicMock

import pytest
from starlette.testclient import TestClient

from cloudops_agent import app as app_module

VALIDATION_MSG = "'prompt' must be a non-empty string"


class FakeAgent:
    def __init__(self, events, error=None):
        self._events = events
        self._error = error
        self.prompts = []

    async def stream_async(self, prompt):
        self.prompts.append(prompt)
        for event in self._events:
            yield event
        if self._error:
            raise self._error


@pytest.fixture
def fake_build(monkeypatch):
    def install(events=(), error=None):
        agent = FakeAgent(list(events), error)
        build = MagicMock(return_value=agent)
        monkeypatch.setattr(app_module, "build_agent", build)
        return build, agent

    return install


@pytest.fixture
def client():
    return TestClient(app_module.app)


def sse_payloads(body: str) -> list:
    return [
        json.loads(line[len("data: ") :]) for line in body.splitlines() if line.startswith("data: ")
    ]


def invoke(client, payload, **kwargs):
    return client.post("/invocations", json=payload, **kwargs)


def test_ping(client):
    assert client.get("/ping").status_code == 200


def test_streams_text_only(client, fake_build):
    fake_build([{"data": "Hel"}, {"current_tool_use": {"name": "aws_read"}}, {"data": "lo"}])
    resp = invoke(client, {"prompt": "hi"})
    assert resp.status_code == 200
    assert sse_payloads(resp.text) == ["Hel", "lo"]
    assert "aws_read" not in resp.text


def test_ignores_empty_and_non_string_data(client, fake_build):
    fake_build([{"data": ""}, {"data": 5}, {"data": "ok"}])
    assert sse_payloads(invoke(client, {"prompt": "hi"}).text) == ["ok"]


@pytest.mark.parametrize(
    "payload", [{}, {"prompt": 5}, {"prompt": None}, {"prompt": "   "}, ["prompt"], "hi"]
)
def test_invalid_prompt(client, fake_build, payload):
    build, _ = fake_build([{"data": "x"}])
    resp = invoke(client, payload)
    assert resp.status_code == 200
    assert VALIDATION_MSG in resp.text
    build.assert_not_called()


def test_prompt_too_long(client, fake_build, monkeypatch):
    build, _ = fake_build([{"data": "x"}])
    monkeypatch.setattr(
        app_module, "settings", app_module.load_settings({"MAX_PROMPT_CHARS": "10"})
    )
    resp = invoke(client, {"prompt": "x" * 11})
    assert "exceeds 10 characters" in resp.text
    build.assert_not_called()


def test_prompt_at_limit_accepted(client, fake_build, monkeypatch):
    fake_build([{"data": "ok"}])
    monkeypatch.setattr(
        app_module, "settings", app_module.load_settings({"MAX_PROMPT_CHARS": "10"})
    )
    assert sse_payloads(invoke(client, {"prompt": "x" * 10}).text) == ["ok"]


def test_exception_mid_stream_is_generic(client, fake_build):
    fake_build([{"data": "a"}], error=RuntimeError("secret internals"))
    resp = invoke(client, {"prompt": "hi"})
    assert resp.status_code == 200
    assert "[error]" in resp.text
    assert "secret internals" not in resp.text
    assert "RuntimeError" not in resp.text


def test_exception_building_agent_is_generic(client, monkeypatch):
    monkeypatch.setattr(app_module, "build_agent", MagicMock(side_effect=ValueError("boom-detail")))
    resp = invoke(client, {"prompt": "hi"})
    assert "[error]" in resp.text
    assert "boom-detail" not in resp.text


def test_session_id_from_payload_passed_to_build_agent(client, fake_build):
    build, agent = fake_build([{"data": "ok"}])
    invoke(client, {"prompt": "hi", "session_id": "x" * 33, "actor_id": "u1"})
    build.assert_called_once_with(app_module.settings, session_id="x" * 33, actor_id="u1")
    assert agent.prompts == ["hi"]


def test_session_id_header_wins_over_payload(client, fake_build):
    build, _ = fake_build([{"data": "ok"}])
    invoke(
        client,
        {"prompt": "hi", "session_id": "p" * 33},
        headers={"X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": "h" * 33},
    )
    assert build.call_args.kwargs["session_id"] == "h" * 33


def test_defaults_without_session_or_actor(client, fake_build):
    build, _ = fake_build([{"data": "ok"}])
    invoke(client, {"prompt": "hi"})
    assert build.call_args.kwargs == {"session_id": None, "actor_id": "default"}


def test_sdk_app_logs_are_emitted_exactly_once():
    """SDK records go to the SDK's own stream handler or to root handlers, never both."""

    class Recorder(logging.Handler):
        def __init__(self):
            super().__init__()
            self.messages = []

        def emit(self, record):
            self.messages.append(record.getMessage())

    recorder = Recorder()
    root = logging.getLogger()
    root.addHandler(recorder)
    try:
        app_module.app.logger.info("sdk-line-marker")
    finally:
        root.removeHandler(recorder)
    sdk_has_own_stream = any(
        isinstance(h, logging.StreamHandler) for h in app_module.app.logger.handlers
    )
    reached_root = "sdk-line-marker" in recorder.messages
    assert reached_root is not sdk_has_own_stream
