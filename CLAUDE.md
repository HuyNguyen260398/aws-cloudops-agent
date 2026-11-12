# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a read-only AWS CloudOps assistant. It is a Strands agent served by `BedrockAgentCoreApp`
on Amazon Bedrock AgentCore Runtime. It uses Python 3.13 and `uv`, and runs in region
`ap-southeast-1`. Terraform provisions all AWS infrastructure. GitHub Actions checks pull
requests and deploys from `main` using OIDC.

## Commands

```bash
uv sync                                              # install (incl. dev group)
uv run pytest                                        # all unit tests (no AWS calls)
uv run pytest tests/test_aws_read.py::test_name      # single test
uv run ruff check . && uv run ruff format --check .  # lint + format check (legacy/ and docs/ excluded)

uv run python -m cloudops_agent.app                  # serve on :8080 (POST /invocations, GET /ping)
uv run python scripts/invoke.py --local -m "..."     # chat with local server
uv run python scripts/invoke.py --runtime-arn ARN    # chat with deployed runtime (interactive)

docker buildx build --platform linux/arm64 -t cloudops-agent:dev --load .
docker run --rm -p 8080:8080 -e OTEL_SDK_DISABLED=true -e AWS_REGION=ap-southeast-1 cloudops-agent:dev

terraform fmt -check -recursive infra
terraform -chdir=infra/bootstrap init -backend=false && terraform -chdir=infra/bootstrap validate
terraform -chdir=infra init -backend=false && terraform -chdir=infra validate
trivy config --severity HIGH,CRITICAL --exit-code 1 infra
```

## Architecture

The package is `src/cloudops_agent/`:

- `config.py`: `load_settings(env)` returns a frozen `Settings` read from environment variables
  (`MODEL_ID`, `MEMORY_ID`, `AWS_REGION`, `LOG_LEVEL`, `MAX_PROMPT_CHARS`, `MAX_TOOL_OUTPUT_CHARS`).
  `DEFAULT_MODEL_ID` must match the `model_id` default in `infra/variables.tf`.
- `app.py`: `@app.entrypoint invoke(payload, context)`. It loads settings once at import and
  validates `prompt`. A bad prompt yields one error string and never builds an agent. Otherwise
  it builds a fresh agent per request and yields only the text `data` events. Any exception is
  logged, and the caller gets only a generic `[error]` line.
- `agent.py`: `build_agent(settings, session_id, actor_id)`. It wires `BedrockModel`, the tools,
  `SYSTEM_PROMPT`, `SummarizingConversationManager`, and a `ContextInjector` for the current
  time. It sets `callback_handler=None`, so nothing prints to stdout. The
  `AgentCoreMemorySessionManager` is used **only when `MEMORY_ID` and a session id are both set**.
- `prompts.py`: the system prompt, which states that the agent is read-only.
- `tools/aws_read.py`: the only AWS tool, built with `make_aws_read_tool(settings, session_factory)`.
- `logging_setup.py`: JSON-line logging to stdout.

**Read-only design, in two layers:**
1. The runtime IAM role has only `agent_read_policy_arns` (default `ReadOnlyAccess`) plus what
   the runtime itself needs.
2. `aws_read` normalizes the operation to snake_case and lower case. It allows only the
   `describe_/list_/get_/lookup_/search_` prefixes and refuses `DENIED_OPERATIONS`, the reads
   that return secrets or credentials, plus `DENIED_SUBSTRINGS` such as "credentials" and
   "password". Both checks run before a boto3 client exists. The tool redacts secret fields
   (environment values, `ClientSecret`, passwords, `UserData`), strips `ResponseMetadata`, and
   truncates its output.
3. The runtime role in `infra/iam.tf` has an explicit `DenySecretAndDataReads`. The deploy role
   may manage only `cloudops-agent-runtime`, attach only `runtime_read_policy_arns`, and pass
   the role only to AgentCore. `tests/test_infra_policies.py` guards these rules.

Do not add `strands-agents-tools`. Its `use_aws` blocks on stdin for consent, which hangs the
server.

**New tool sets** go in `src/cloudops_agent/tools/` (for example `tools/spacelift/`) and are
registered in the `tools=[...]` list in `build_agent`. Make them factories that take `Settings`,
so tests can inject fakes.

`scripts/invoke.py` is a client for either the local server or `InvokeAgentRuntime`. AgentCore
requires session IDs of at least 33 characters, and the client generates one when none is given.

## Infrastructure and CI

- `infra/bootstrap/`: applied once by an admin, with **local state**. It creates the S3 state
  bucket, the GitHub OIDC provider, the deploy role (trusted only for
  `repo:<owner/name>:environment:production`), and the ECR repo (immutable tags).
- `infra/`: uses the S3 backend (`cloudops-agent/prod.tfstate`, `use_lockfile`). It creates the
  AgentCore runtime `cloudops_agent`, the endpoint `cloudops_agent_live` (which follows the latest
  runtime version), the memory, the runtime IAM role, and log groups named
  `/aws/bedrock-agentcore/runtimes/<runtime-id>-<endpoint>`. Do not hard-code account IDs or
  ARNs; use data sources and variables.
- `.github/workflows/ci.yml` runs on PRs and on `main`. It runs ruff, pytest, terraform
  fmt/validate, trivy, gitleaks over the full history, and an arm64 docker build.
- `.github/workflows/deploy.yml` runs on `main` and needs approval of the `production`
  environment. It assumes the deploy role over OIDC, builds and pushes `<ecr>:<sha>` (skipped if
  that tag already exists), then runs `terraform apply`.
- Actions are pinned to full commit SHAs, with the tag in a comment. Base images are pinned by
  digest.

## legacy/

`legacy/` holds the old FastAPI runtime, the Lambdas, the KB/RAG Terraform, the
Cognito/Gateway glue, the old workflows, and their docs. It is **not maintained, built, tested,
or linted**. Do not import from it or fix it unless asked.
