import importlib.util
import json
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "invoke.py"
_spec = importlib.util.spec_from_file_location("invoke_script", _PATH)
invoke = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(invoke)


def test_new_session_id_long_enough_and_unique():
    a, b = invoke.new_session_id(), invoke.new_session_id()
    assert len(a) >= 33
    assert a != b


def test_build_payload():
    assert json.loads(invoke.build_payload("hi", "s" * 33, "u")) == {
        "prompt": "hi",
        "session_id": "s" * 33,
        "actor_id": "u",
    }


def test_short_session_id_rejected():
    with pytest.raises(SystemExit) as exc:
        invoke.main(["--session-id", "short", "-m", "hi", "--local"])
    assert exc.value.code != 0


def test_remote_without_runtime_arn_rejected(monkeypatch):
    monkeypatch.delenv("AGENT_RUNTIME_ARN", raising=False)
    with pytest.raises(SystemExit) as exc:
        invoke.main(["-m", "hi"])
    assert exc.value.code != 0


def test_parse_sse_lines():
    lines = [b'data: "Hel"', b"", b'data: "lo"', b"data: not-json", b": comment"]
    assert list(invoke.iter_sse_text(lines)) == ["Hel", "lo", "not-json"]


def test_remote_invocation_uses_boto3(monkeypatch, capsys):
    calls = {}

    class Body:
        def iter_lines(self):
            return iter([b'data: "Hi"', b"", b'data: " there"'])

    class Client:
        def invoke_agent_runtime(self, **kwargs):
            calls.update(kwargs)
            return {"contentType": "text/event-stream", "response": Body()}

    monkeypatch.setattr(invoke.boto3, "client", lambda *a, **k: Client())
    rc = invoke.main(["--runtime-arn", "arn:x", "--session-id", "s" * 33, "-m", "hello"])
    assert rc == 0
    assert calls["agentRuntimeArn"] == "arn:x"
    assert calls["runtimeSessionId"] == "s" * 33
    assert calls["qualifier"] == "cloudops_agent_live"
    assert json.loads(calls["payload"])["prompt"] == "hello"
    assert "Hi there" in capsys.readouterr().out
