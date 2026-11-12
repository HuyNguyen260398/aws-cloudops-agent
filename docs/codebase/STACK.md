# Technology Stack

> Part of the onboarding set. Start at [../ONBOARDING.md](../ONBOARDING.md).

## 1) Runtime Summary

| Area | Value | Evidence |
|------|-------|----------|
| Primary language | Python | `pyproject.toml`, `src/cloudops_agent/` |
| Runtime + version | Python 3.13 (`requires-python = ">=3.13"`) | `.python-version`, `pyproject.toml`, `Dockerfile` (base `python:3.13-slim-bookworm`) |
| Package manager | uv 0.11+ (`uv.lock` committed, no `requirements.txt`) | `uv.lock`, `pyproject.toml` `[tool.uv] package = true` |
| Module/build system | hatchling wheel; package `src/cloudops_agent` | `pyproject.toml` `[build-system]`, `[tool.hatch.build.targets.wheel]` |
| Container | linux/arm64, two stages (uv builder, then slim runtime), non-root uid 1000 | `Dockerfile` |
| Infrastructure as code | Terraform ≥ 1.15, `hashicorp/aws ~> 6.72` (6.73.0 locked) | `infra/versions.tf`, `infra/.terraform.lock.hcl` |
| Hosting | Amazon Bedrock AgentCore Runtime, region `ap-southeast-1` | `infra/runtime.tf`, `infra/variables.tf` |
| CI/CD | GitHub Actions | `.github/workflows/ci.yml`, `.github/workflows/deploy.yml` |

## 2) Production Frameworks and Dependencies

These are the only direct runtime dependencies, and each is pinned exactly:

| Dependency | Version | Role in system | Evidence |
|------------|---------|----------------|----------|
| `strands-agents` | 1.64.0 | Agent loop, `@tool` decorator, `BedrockModel`, `SummarizingConversationManager`, `ContextInjector` plugin | `pyproject.toml`, `src/cloudops_agent/agent.py` |
| `bedrock-agentcore` | 1.26.0 | `BedrockAgentCoreApp` (Starlette/uvicorn HTTP server: `/invocations`, `/ping`, SSE), `RequestContext`, Strands memory session manager | `src/cloudops_agent/app.py`, `src/cloudops_agent/agent.py` |
| `boto3` | 1.44.0 | AWS SDK used by `aws_read` and `scripts/invoke.py` | `src/cloudops_agent/tools/aws_read.py`, `scripts/invoke.py` |
| `aws-opentelemetry-distro` | 0.22.0 | `opentelemetry-instrument` wrapper in the container CMD (traces and metrics to X-Ray/CloudWatch) | `Dockerfile` `CMD`, `pyproject.toml` |

Notable transitive packages (from `uv.lock`): Starlette 0.48.0, uvicorn 0.37.0 and pydantic 2.14.3,
all pulled in by `bedrock-agentcore`.

**Deliberately not used:** `strands-agents-tools`. Its `use_aws` tool waits for console
input to confirm an action, which hangs a server, and `current_time` was removed from it. The
replacements are `aws_read` and the `ContextInjector` (evidence: `CLAUDE.md`,
the repo-modernization implementation plan, Global Constraints).

## 3) Development Toolchain

| Tool | Purpose | Evidence |
|------|---------|----------|
| ruff 0.17.4 | Lint (`E,F,I,B,UP,S`) and format; line length 100; excludes `legacy/` and `docs/` | `pyproject.toml` `[tool.ruff]` |
| pytest 9.2.0 | Unit tests (`pythonpath = ["src"]`, `testpaths = ["tests"]`) | `pyproject.toml` `[tool.pytest.ini_options]` |
| httpx 0.28.1 | Required by Starlette `TestClient` in `tests/test_app.py` | `pyproject.toml` dev group |
| trivy | Terraform misconfiguration scan (HIGH/CRITICAL) | `.github/workflows/ci.yml` (`aquasecurity/trivy-action`) |
| gitleaks v8.30.x | Secret scanning (CI over the full history, and pre-commit) | `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, `.gitleaks.toml` |
| pre-commit (run via `uvx`) | gitleaks, ruff-check, ruff-format, terraform_fmt hooks | `.pre-commit-config.yaml` |
| actionlint | Workflow lint (run locally; not part of CI) | `[TODO]` not wired into CI; it was run by hand during the modernization |
| Docker buildx + QEMU | arm64 image builds | `Dockerfile`, both workflows |

## 4) Key Commands

```bash
uv sync                                              # install runtime + dev deps
uv run pytest                                        # tests
uv run ruff check . && uv run ruff format --check .  # lint + format check
uv run python -m cloudops_agent.app                  # run server on :8080
uv run python scripts/invoke.py --local              # chat with local server
docker buildx build --platform linux/arm64 -t cloudops-agent:dev --load .
terraform -chdir=infra init -backend=false && terraform -chdir=infra validate
```

## 5) Environment and Config

- **Config sources:** environment variables only, read once by `load_settings()` in
  `src/cloudops_agent/config.py`. Terraform sets them on the runtime (`infra/runtime.tf`). For
  local runs, use an optional `.env` (copied from `.env.example`) with `uv run --env-file .env`.
- **Variables:**

  | Variable | Default | Notes |
  |---|---|---|
  | `MODEL_ID` | `global.anthropic.claude-sonnet-5-5` | |
  | `MEMORY_ID` | unset | Memory is off when unset |
  | `AWS_REGION` | `AWS_DEFAULT_REGION`, then `ap-southeast-1` | |
  | `LOG_LEVEL` | `INFO` | |
  | `MAX_PROMPT_CHARS` | `10000` | |
  | `MAX_TOOL_OUTPUT_CHARS` | `20000` | |

  None of them is required.
- **Client-only variable:** `AGENT_RUNTIME_ARN` (`scripts/invoke.py`).
- **Container-only variables:** `DOCKER_CONTAINER=1` makes the SDK bind to `0.0.0.0`.
  `OTEL_SDK_DISABLED=true` is recommended for local `docker run`.
- **Deployment constraints:**
  - AgentCore Runtime needs a **linux/arm64** image that listens on **port 8080**.
  - Session IDs must be **at least 33 characters**.
  - The default model ID must be kept in sync by hand in two places: `config.py`
    `DEFAULT_MODEL_ID` and `infra/variables.tf` `model_id`.

## 6) Evidence

- `pyproject.toml`, `uv.lock`, `.python-version`
- `Dockerfile`, `.dockerignore`
- `src/cloudops_agent/config.py`, `.env.example`
- `infra/versions.tf`, `infra/bootstrap/versions.tf`, `infra/.terraform.lock.hcl`
- `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `.pre-commit-config.yaml`
