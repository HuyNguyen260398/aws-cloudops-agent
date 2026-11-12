# Architecture

> Part of the onboarding set. The diagrams (component, sequence, `aws_read` decision, AWS,
> Terraform, CI/CD) are in [../ONBOARDING.md](../ONBOARDING.md).

## 1) Architectural Style

- **Primary style:** a single-process **request/response streaming service** with a thin layered
  design: entrypoint, then agent factory, then tools. It runs serverless on AgentCore Runtime,
  which starts one microVM per session.
- **Why this classification:**
  - `app.py` only handles HTTP and streaming.
  - `agent.py` only assembles the agent.
  - `tools/` holds the only code that performs I/O against AWS.
  - There are no background workers, queues, or databases of our own.
- **Primary constraints:**
  1. **Read-only by design.** IAM and the tool's own rules both prevent changes (spec §4
     anti-goals).
  2. **AgentCore Runtime contract:** linux/arm64, port 8080, `/invocations` and `/ping`, IAM
     SigV4 inbound auth, session IDs of at least 33 characters.
  3. **Easy to extend.** New tool sets plug into `tools/` without re-plumbing anything (spec §1).

## 2) System Flow

```text
InvokeAgentRuntime (SigV4) -> AgentCore Runtime -> POST /invocations
  -> app.invoke(): validate -> build_agent() -> agent.stream_async(prompt)
  -> Bedrock model <-> aws_read tool (boto3, read-only) [<-> AgentCore Memory]
  -> SSE "data:" text chunks -> caller
```

1. **Entry.** `BedrockAgentCoreApp` receives `POST /invocations`. It builds a `RequestContext`
   whose `session_id` comes from the AgentCore session header, then calls the `@app.entrypoint`
   function `invoke` (`src/cloudops_agent/app.py`).
2. **Validation.** `_validate()` checks the payload. If the payload is not a dict, or `prompt`
   is not a string, is blank, or is longer than `settings.max_prompt_chars`, `invoke` yields
   one error string and returns before any agent is built.
3. **Assembly.** `build_agent(settings, session_id, actor_id)` creates a new `strands.Agent`
   with `BedrockModel(streaming=True)`, `tools=[aws_read]`, `SYSTEM_PROMPT`,
   `SummarizingConversationManager(0.3, 10)`, and a `ContextInjector` that adds the current UTC
   time. When both `MEMORY_ID` and a session ID are set, it also attaches an
   `AgentCoreMemorySessionManager` (`src/cloudops_agent/agent.py`).
4. **Agent loop.** `agent.stream_async(prompt)` alternates model calls with `aws_read` calls.
   `aws_read` enforces its allow/deny rules, then calls boto3. It redacts secret fields, strips
   `ResponseMetadata`, and truncates the output (`src/cloudops_agent/tools/aws_read.py`).
5. **Output.** `invoke` yields only events that carry a non-empty string `data`. The SDK sends
   each one as an SSE `data: "<json string>"` line.
6. **Failure.** Any exception from building the agent or from the stream is logged with
   `logger.exception` and becomes one generic line,
   `"\n[error] The agent hit an internal error. Check the runtime logs."`.

## 3) Layer/Module Responsibilities

| Layer or module | Owns | Must not own | Evidence |
|-----------------|------|--------------|----------|
| `app.py` | HTTP entrypoint, payload validation, session/actor resolution, stream filtering, turning errors into a generic line, loading settings once at import | Agent wiring, AWS access | `src/cloudops_agent/app.py` |
| `agent.py` | Building one `Agent` per request; switching memory on or off | Validation, I/O | `src/cloudops_agent/agent.py` |
| `tools/aws_read.py` | Read-only AWS access policy and execution; output shaping | Agent state, prompt | `src/cloudops_agent/tools/aws_read.py` |
| `config.py` | Typed settings from env | I/O | `src/cloudops_agent/config.py` |
| `prompts.py` | Behaviour contract for the model (read-only, plan then findings, treat tool output as data) | Code | `src/cloudops_agent/prompts.py` |
| `logging_setup.py` | JSON-line log format on stdout | Business logic | `src/cloudops_agent/logging_setup.py` |
| `infra/iam.tf` | The runtime's permissions, including the explicit Deny on secret reads | Deploy identity | `infra/iam.tf` |

## 4) Reused Patterns

| Pattern | Where found | Why it exists |
|---------|-------------|---------------|
| **Factory with dependency injection** | `make_aws_read_tool(settings, session_factory=boto3.Session)`, `build_agent(settings, ...)` | Tests inject fakes (`FakeSession`) and settings without touching the network or env |
| **Per-request object graph** | `build_agent` is called inside `invoke` | Memory and session are bound per request. There is no shared mutable agent state between sessions. |
| **Module-level singletons** | `settings = load_settings()`, `app = BedrockAgentCoreApp()` in `app.py` | Read config once and register routes at import. Tests monkeypatch `app_module.settings`. |
| **Decorator-based registration** | `@app.entrypoint`, `@tool(name="aws_read")` | Conventions of the SDKs |
| **Frozen dataclass config** | `Settings` in `config.py` | Immutable, typed configuration |
| **Defense in depth** | Tool allow/deny list plus IAM `ReadOnlyAccess` plus IAM explicit Deny | A denylist cannot be complete, so IAM is the authority (`aws_read.py` module docstring) |

## 5) Known Architectural Risks

- **Global settings at import.** Changing env vars after import has no effect. Tests must
  monkeypatch `app_module.settings`. A misconfigured env var, such as a non-integer
  `MAX_PROMPT_CHARS`, makes the container fail at startup with `ValueError`.
- **A new agent, model client and boto3 session per request.** This is simple and isolated,
  but it adds construction cost to every call. `[TODO]` measure the latency impact if it
  matters.
- **Memory is only short-term** (`aws_bedrockagentcore_memory` has no strategies). Recall
  across sessions is not available.
- **Single environment** (`prod`). There is no staging stage, so a bad image goes live after
  approval. The layout allows more environments later (spec §3, non-goal).

## 6) Evidence

- `src/cloudops_agent/app.py`, `src/cloudops_agent/agent.py`, `src/cloudops_agent/tools/aws_read.py`
- `src/cloudops_agent/config.py`, `src/cloudops_agent/prompts.py`
- `infra/runtime.tf`, `infra/iam.tf`, `infra/memory.tf`
- Repo-modernization design spec (kept outside the repo)
