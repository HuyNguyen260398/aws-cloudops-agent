# Testing Patterns

> Part of the onboarding set. Start at [../ONBOARDING.md](../ONBOARDING.md).

## 1) Test Stack and Commands

- **Framework:** pytest 9.2.0 with plain `assert`. `unittest.mock.MagicMock` is used
  sparingly. Starlette `TestClient`, which needs `httpx`, drives the HTTP app in-process.
- **Commands:**

```bash
uv run pytest                                   # all tests (83, ~1 s, no AWS calls)
uv run pytest tests/test_aws_read.py            # one file
uv run pytest tests/test_aws_read.py::test_client_error_reported   # one test
uv run pytest -k redact -v                      # by keyword
# coverage: not configured [TODO] (e.g. add pytest-cov to the dev group)
```

- **Other checks run in CI** (`.github/workflows/ci.yml`):
  - `ruff check` and `ruff format --check`;
  - `terraform fmt -check`, plus `validate` for both configs;
  - `trivy config` (HIGH/CRITICAL);
  - gitleaks over the full history;
  - an arm64 `docker build`.

## 2) Test Layout

- **Placement:** a separate `tests/` folder, configured by `testpaths = ["tests"]`. `src/` is
  importable through `pythonpath = ["src"]` (`pyproject.toml`).
- **Naming:** `tests/test_<module>.py` holds functions named `test_<behaviour>`.
- **Shared setup:** there is no `conftest.py`. Fixtures are local to each file, for example
  `fake_build` and `client` in `tests/test_app.py`, and `session_manager_cls` in
  `tests/test_agent.py`.
- **Script under test:** `tests/test_invoke_script.py` loads `scripts/invoke.py` with
  `importlib`, because `scripts/` is not a package.

| File | Covers |
|------|--------|
| `test_config.py` | Defaults, env overrides, region fallback, blank `MEMORY_ID`, invalid integers |
| `test_aws_read.py` | Allow/deny rules in many casings, refusals never calling boto3, unknown operations, JSON output, truncation, `ClientError` text, region passthrough, redaction of secret fields |
| `test_agent.py` | Tool list is exactly `["aws_read"]`, model ID and prompt wiring, memory on/off rules, prompt says read-only |
| `test_app.py` | `/ping`; text-only streaming; invalid, non-string, blank, non-dict and oversized prompts; generic errors mid-stream and at build time; session/actor resolution (header beats payload); SDK logs emitted once |
| `test_logging_setup.py` | Single-line JSON format and idempotent setup |
| `test_invoke_script.py` | Session ID length and uniqueness, payload shape, short session ID rejected, missing ARN rejected, SSE parsing, remote call arguments |
| `test_infra_policies.py` | Static checks on the Terraform text: the deploy role cannot edit itself, PassRole and Attach are restricted, and the runtime role denies secret reads |

## 3) Test Scope Matrix

| Scope | Covered? | Typical target | Notes |
|-------|----------|----------------|-------|
| Unit | Yes | All modules in `src/cloudops_agent`, `scripts/invoke.py` | No AWS or network |
| Integration (in-process HTTP) | Yes | `BedrockAgentCoreApp` through `TestClient` | The agent is faked |
| Static infrastructure | Partial | IAM policy shape through regex over `.tf` files | `tests/test_infra_policies.py` is text-based and brittle on purpose |
| Live AWS / Bedrock | No (manual) | Smoke test: run the app, then `scripts/invoke.py --local` | Needs credentials; see `README.md` |
| E2E against the deployed runtime | No | `scripts/invoke.py` with `AGENT_RUNTIME_ARN` | `[TODO]` post-deploy smoke step in `deploy.yml` |
| Container | Partial | CI builds the arm64 image | The image is not run in CI. `[TODO]` add a ping check. |

## 4) Mocking and Isolation Strategy

- **Injection first:**
  - `make_aws_read_tool(settings, session_factory=lambda: FakeSession(FakeClient(...)))`.
  - `FakeClient.meta.method_to_api_mapping` mimics botocore's operation lookup.
- **Monkeypatching module attributes:**
  - `app_module.build_agent` is replaced with a `MagicMock` that returns a `FakeAgent`, whose
    `stream_async` is an async generator.
  - `app_module.settings` is replaced to change limits.
  - `agent_module.AgentCoreMemorySessionManager` is replaced to observe memory wiring.
- **Isolation:** `monkeypatch` undoes every patch after each test. Settings are built from
  explicit dicts (`load_settings({...})`) and never from the real environment.
- **Common pitfalls:**
  - `app.py` reads settings at import, so patch `app_module.settings`, not env vars.
  - pytest's logging plugin attaches handlers to loggers, which changes how the SDK logger
    behaves under test. `test_sdk_app_logs_are_emitted_exactly_once` checks routing rather than
    counting printed lines for this reason.

## 5) Coverage and Quality Signals

- **Coverage tool and threshold:** none. `[TODO]`
- **Current coverage:** `[TODO]` not measured.
- **Known gaps:**
  - No live tests.
  - No container run in CI.
  - `test_infra_policies.py` relies on how the Terraform files are laid out.
  - Third-party deprecation warnings (about 19, from `bedrock_agentcore` and `strands`) show
    in pytest output and are expected.

## 6) Evidence

- `pyproject.toml` (`[tool.pytest.ini_options]`, dev group)
- `tests/test_app.py`, `tests/test_aws_read.py`, `tests/test_agent.py`, `tests/test_infra_policies.py`
- `.github/workflows/ci.yml`
