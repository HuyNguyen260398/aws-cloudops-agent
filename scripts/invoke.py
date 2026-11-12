"""Chat with the CloudOps agent, locally (http://localhost:8080) or on AgentCore Runtime.

Examples:
    uv run python scripts/invoke.py --local -m "How many S3 buckets do I have?"
    uv run python scripts/invoke.py --runtime-arn "$AGENT_RUNTIME_ARN"     # interactive
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import uuid
from collections.abc import Iterable, Iterator

import boto3
from botocore.config import Config

LOCAL_URL = "http://localhost:8080/invocations"
MIN_SESSION_ID_LEN = 33  # AgentCore runtimeSessionId minimum


def new_session_id() -> str:
    return "cli-" + uuid.uuid4().hex  # 36 characters


def build_payload(prompt: str, session_id: str, actor_id: str) -> bytes:
    return json.dumps({"prompt": prompt, "session_id": session_id, "actor_id": actor_id}).encode()


def iter_sse_text(lines: Iterable[bytes | str]) -> Iterator[str]:
    """Yield the text of each SSE `data:` line (JSON-decoded when possible)."""
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        line = line.rstrip("\r\n")
        if not line.startswith("data:"):
            continue
        data = line[len("data:") :].strip()
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            value = data
        yield value if isinstance(value, str) else json.dumps(value)


def _print_stream(chunks: Iterable[str]) -> None:
    for chunk in chunks:
        print(chunk, end="", flush=True)
    print()


def _invoke_local(payload: bytes) -> None:
    req = urllib.request.Request(  # noqa: S310 - fixed localhost URL
        LOCAL_URL, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        _print_stream(iter_sse_text(resp))


def _invoke_remote(client, runtime_arn: str, qualifier: str, session_id: str, payload: bytes):
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=runtime_arn,
        runtimeSessionId=session_id,
        qualifier=qualifier,
        payload=payload,
    )
    body = resp["response"]
    if "text/event-stream" in resp.get("contentType", ""):
        _print_stream(iter_sse_text(body.iter_lines()))
    else:
        print(body.read().decode("utf-8"))


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--local", action="store_true", help=f"POST to {LOCAL_URL}")
    p.add_argument("--runtime-arn", default=os.environ.get("AGENT_RUNTIME_ARN"))
    p.add_argument("--qualifier", default="cloudops_agent_live")
    p.add_argument("--session-id", default=None, help="reuse a session (>= 33 chars)")
    p.add_argument("--actor-id", default="default")
    p.add_argument("-m", "--message", default=None, help="send one message and exit")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    session_id = args.session_id or new_session_id()
    if len(session_id) < MIN_SESSION_ID_LEN:
        sys.exit(f"error: --session-id must be at least {MIN_SESSION_ID_LEN} characters")
    if not args.local and not args.runtime_arn:
        sys.exit("error: pass --runtime-arn or set AGENT_RUNTIME_ARN (or use --local)")

    client = None
    if not args.local:
        client = boto3.client("bedrock-agentcore", config=Config(read_timeout=300))

    def send(prompt: str) -> None:
        payload = build_payload(prompt, session_id, args.actor_id)
        if args.local:
            _invoke_local(payload)
        else:
            _invoke_remote(client, args.runtime_arn, args.qualifier, session_id, payload)

    if args.message is not None:
        send(args.message)
        return 0

    print(f"session: {session_id}  (type 'exit' or 'quit' to leave)")
    while True:
        try:
            prompt = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if prompt.lower() in {"exit", "quit"}:
            return 0
        if prompt:
            send(prompt)


if __name__ == "__main__":
    sys.exit(main())
