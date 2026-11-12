# Coding Conventions

> Part of the onboarding set. Start at [../ONBOARDING.md](../ONBOARDING.md).

## 1) Naming Rules

| Item | Rule | Example | Evidence |
|------|------|---------|----------|
| Files | `snake_case.py`; tests `test_<module>.py` | `logging_setup.py`, `tests/test_aws_read.py` | `src/cloudops_agent/`, `tests/` |
| Functions/methods | `snake_case`; leading `_` for module-private helpers | `build_agent`, `_validate`, `_redact` | `app.py`, `aws_read.py` |
| Factories | `make_<thing>` / `build_<thing>` | `make_aws_read_tool`, `build_agent` | `tools/aws_read.py`, `agent.py` |
| Types | `PascalCase` | `Settings`, `JsonFormatter` | `config.py`, `logging_setup.py` |
| Constants | `UPPER_SNAKE` at module level | `DEFAULT_MODEL_ID`, `DENIED_OPERATIONS`, `INTERNAL_ERROR_MSG` | `config.py`, `aws_read.py`, `app.py` |
| Env vars | `UPPER_SNAKE` | `MAX_TOOL_OUTPUT_CHARS` | `config.py` |
| Terraform | `snake_case` resource labels; one concern per file; comments explain every `*` resource | `aws_iam_role.runtime`, `# Required by AWS: ...` | `infra/iam.tf` |

## 2) Formatting and Linting

- **Formatter:** `ruff format`, configured in `pyproject.toml` `[tool.ruff]`
  (`line-length = 100`, `target-version = "py313"`).
- **Linter:** `ruff check` with `select = ["E","F","I","B","UP","S"]`. `S101` (assert) is
  ignored under `tests/**`. `legacy/` and `docs/` are excluded.
- **Rules that matter most:**
  - `S`: bandit security checks. They are why `scripts/invoke.py` carries
    `# noqa: S310` on its fixed-localhost `urlopen`.
  - `I`: import sorting.
  - `UP`: modern syntax, for example `str | None` and `datetime.UTC`.
- **Terraform:** `terraform fmt -check -recursive infra`, enforced in CI and in pre-commit.
- **Commands:** `uv run ruff check . && uv run ruff format --check .` (CI runs exactly these).
  To fix: `uv run ruff check --fix . && uv run ruff format .`.

## 3) Import and Module Conventions

- **Ordering:** `from __future__ import annotations` first, then stdlib, third-party, and local
  groups, sorted by ruff `I`.
- **Absolute imports only** (`from cloudops_agent.tools import make_aws_read_tool`). There are
  no relative imports and no aliases.
- **Public exports:** `tools/__init__.py` re-exports the tool factories through `__all__`.
  Other modules are imported directly.

## 4) Error and Logging Conventions

- **Errors by layer:**
  - **Entrypoint (`app.py`):** validation failures are *yielded* as a user-facing string, never
    raised. Unexpected exceptions are caught, logged with `logger.exception`, and replaced by
    `INTERNAL_ERROR_MSG`. **Exception text must never reach the caller.**
  - **Tools (`aws_read.py`):** tools *return strings* for every expected failure, so the model
    can read them and adapt:
    - `Refused: ...` for policy denials;
    - `AWS error <Code>: <Message>` for a botocore `ClientError`;
    - `AWS error: ...` for a `BotoCoreError`.
  - **Config (`config.py`):** raises `ValueError` with the variable name when an integer
    variable is invalid. This fails fast at startup.
- **Logging:**
  - Use `logging.getLogger(__name__)`.
  - `configure_logging()` writes one JSON object per line to stdout, with the keys `time`,
    `level`, `logger`, `message` and, when present, `exc_info`.
  - The AgentCore SDK logger (`bedrock_agentcore.app`) keeps its own JSON handler, which adds
    `requestId`, and does not propagate.
- **Sensitive data:**
  - Never log or stream secrets.
  - `aws_read` redacts environment-variable values, `ClientSecret`, `SecretString`,
    `UserData`, password-like fields and similar before the model sees them.
  - The system prompt tells the model never to reveal secrets and to treat tool output as data.

## 5) Testing Conventions

- **Location:** tests live in `tests/test_<module>.py` and use plain pytest functions and
  `assert`.
- **Mocking:**
  - Inject fakes through factory arguments (`FakeSession`/`FakeClient` in
    `tests/test_aws_read.py`).
  - Use `monkeypatch.setattr` on module attributes (`app_module.build_agent`,
    `agent_module.AgentCoreMemorySessionManager`).
  - Avoid network mocks.
- **TDD:** each behaviour got a test that failed before it passed (see the modernization plan).
  `[ASK USER]` should TDD be a written team rule?
- **Coverage:** no threshold is configured. `[TODO]`

## 6) Evidence

- `pyproject.toml` (`[tool.ruff]`, `[tool.pytest.ini_options]`)
- `.pre-commit-config.yaml`
- `src/cloudops_agent/app.py`, `src/cloudops_agent/tools/aws_read.py`, `src/cloudops_agent/logging_setup.py`
- `tests/test_aws_read.py`, `tests/test_app.py`
