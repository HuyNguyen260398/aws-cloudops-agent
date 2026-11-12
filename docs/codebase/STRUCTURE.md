# Codebase Structure

> Part of the onboarding set. Start at [../ONBOARDING.md](../ONBOARDING.md).

## 1) Top-Level Map

```text
.
├── src/cloudops_agent/      # the agent package (the only code that ships in the image)
│   ├── app.py               #   AgentCore entrypoint: validate payload, stream text
│   ├── agent.py             #   build_agent(): model, tools, prompt, memory, conversation mgr
│   ├── config.py            #   Settings dataclass + load_settings() from env
│   ├── prompts.py           #   SYSTEM_PROMPT
│   ├── logging_setup.py     #   JSON-line logging
│   └── tools/
│       ├── __init__.py      #   re-exports make_aws_read_tool, is_allowed_operation
│       └── aws_read.py      #   read-only boto3 tool (allow/deny, redact, truncate)
├── scripts/invoke.py        # CLI chat client (local HTTP or InvokeAgentRuntime)
├── tests/                   # pytest unit tests (no AWS calls)
├── infra/                   # Terraform: runtime, endpoint, memory, IAM, logs (S3 backend)
│   └── bootstrap/           # Terraform: state bucket, GitHub OIDC, deploy role, ECR (local state)
├── .github/workflows/       # ci.yml (checks), deploy.yml (OIDC deploy)
├── docs/                    # onboarding, codebase docs, roadmap, specs/plans, diagrams
├── legacy/                  # previous implementation — unmaintained, not built/tested/linted
├── Dockerfile, .dockerignore
├── pyproject.toml, uv.lock, .python-version
├── .env.example, .gitleaks.toml, .gitleaksignore, .pre-commit-config.yaml
├── README.md                # setup, deploy, configuration, security
└── CLAUDE.md                # guidance for Claude Code (commands + architecture)
```

| Path | Purpose | Evidence |
|------|---------|----------|
| `src/cloudops_agent/` | Production Python package | `pyproject.toml` `packages = ["src/cloudops_agent"]` |
| `scripts/` | Developer client and not in the image (`.dockerignore` excludes `scripts`) | `scripts/invoke.py`, `.dockerignore` |
| `tests/` | Unit tests | `pyproject.toml` `testpaths` |
| `infra/` | Agent stack Terraform | `infra/*.tf` |
| `infra/bootstrap/` | One-time admin Terraform | `infra/bootstrap/versions.tf` (comment: local state) |
| `.github/workflows/` | CI and deploy pipelines | `ci.yml`, `deploy.yml` |
| `docs/*.drawio*`, `docs/AWS-CloudOps-Agent.pptx` | **Old** architecture diagrams and deck. They show Cognito, Gateway and the Knowledge Base, which are no longer used. | `docs/aws_agent.drawio` (labels "AgentCore Gateway", "AWS Cognito", "Knowledge Bases") |
| `docs/diagrams/` | Current AWS architecture diagram (draw.io) | `docs/diagrams/aws-architecture.drawio` |
| `legacy/` | Old FastAPI runtime, Lambdas, CloudFormation, KB/RAG Terraform, old workflows and docs | `legacy/README.md` |

## 2) Entry Points

- **Main runtime entry:** `python -m cloudops_agent.app`. `app.run(port=8080)` runs under
  `if __name__ == "__main__"` (`src/cloudops_agent/app.py`). In the container, the CMD wraps
  it as `opentelemetry-instrument python -m cloudops_agent.app` (`Dockerfile`).
- **HTTP routes,** provided by `BedrockAgentCoreApp`: `POST /invocations`, which goes to the
  `@app.entrypoint` function `invoke`, and `GET /ping`.
- **Secondary entry:** `scripts/invoke.py` `main(argv)`, a CLI client.
- **Infrastructure entry points:** `terraform -chdir=infra/bootstrap apply` (admin, once) and
  `terraform -chdir=infra apply` (CI, `deploy.yml`).

## 3) Module Boundaries

| Boundary | What belongs here | What must not be here |
|----------|-------------------|------------------------|
| `app.py` | HTTP payload validation, session/actor resolution, streaming, turning exceptions into a generic error line | Agent wiring, AWS calls, prompt text |
| `agent.py` | Assembling the Strands `Agent` (model, tools, plugins, memory) | Request parsing, HTTP concerns, tool logic |
| `config.py` | Reading and typing env vars | Any I/O other than reading env |
| `tools/` | Tool factories that return Strands `AgentTool`s; future `tools/spacelift/`, `tools/slack/` | Agent construction; module-level clients (inject them through factory args) |
| `prompts.py` | Prompt text constants | Logic |
| `infra/bootstrap/` | Resources needed *before* the agent stack exists (state, OIDC, deploy role, ECR) | Agent runtime resources |
| `infra/` | Agent runtime resources | State bucket, CI identity |
| `legacy/` | Reference only | Anything imported by active code |

## 4) Naming and Organization Rules

- **Python files:** `snake_case.py` (`aws_read.py`, `logging_setup.py`). Tests are named
  `tests/test_<module>.py`.
- **Terraform:** one file per concern (`iam.tf`, `memory.tf`, `runtime.tf`, `variables.tf`,
  `outputs.tf`, `providers.tf`, `versions.tf`). Resource names use `snake_case`. AWS resource
  names follow the plan:
  - runtime `cloudops_agent`;
  - endpoint `cloudops_agent_live`;
  - memory `cloudops_agent_memory`;
  - ECR `cloudops-agent`;
  - IAM roles `cloudops-agent-runtime` and `cloudops-agent-github-deploy`.
- **Organization:** by layer within one small package.
- **Imports:** absolute (`from cloudops_agent.config import ...`). There are no path aliases.
  `src/` is on `sys.path` for tests through pytest's `pythonpath`.

## 5) Evidence

- `pyproject.toml`, `Dockerfile`, `.dockerignore`
- `src/cloudops_agent/app.py`, `src/cloudops_agent/agent.py`, `src/cloudops_agent/tools/__init__.py`
- `infra/runtime.tf`, `infra/bootstrap/main.tf`
- `legacy/README.md`, `docs/codebase/.codebase-scan.txt` (directory tree)
