# Repo Modernization — Design

Date: 2026-11-11
Status: Draft for approval
Related: `2026-11-11-spacelift-plan-summary-agent-design.md` (parked, builds on this)

## 1. Intent

The DevOps team will use this repo as the base for a hackathon about AI agents in DevOps. Its first use case is the Spacelift plan-summary agent, which is parked for now. The repo has not been updated in a while. This work gets it **hackathon-ready**:

- the agent runs on current AWS Bedrock AgentCore and Strands Agents practice,
- all AWS infrastructure for the agent is provisioned by Terraform,
- the repo is secure by default.

New features such as Spacelift can then be added as tools without re-plumbing anything.

## 2. Goals

1. **Modern agent core.** A Strands agent served by the `bedrock-agentcore` SDK on AgentCore Runtime, using a current Claude model on Bedrock and current library versions. It is structured so new tool sets (Spacelift, Slack) plug in cleanly.
2. **Terraform for everything the agent needs.** This replaces `src/ops/deploy_*.py`, the hand-run ECR/IAM commands in `docs/notes.txt`, and the ARNs kept by hand in `config/dynamic-config.yaml`.
3. **Security hardening.** Remove secrets from tracked files, apply least privilege, make the agent read-only on AWS by default, keep CI free of static keys, and add secret scanning.
4. **Developer workflow.** One-command local run, unit tests, lint, and CI that checks and deploys.
5. **Legacy move.** The ping monitor, approval/remediation Lambdas, KB/RAG, Cognito/Gateway glue, and their docs and scripts move to `legacy/`.

## 3. Non-goals

- The Spacelift feature itself (parked).
- Modernizing or deploying anything in `legacy/`.
- Rewriting git history to purge leaked secrets. The team rotates them instead; the README documents this.
- Multi-account or multi-environment promotion. The layout allows it later.

## 4. Anti-goals

- The agent can change AWS resources by default.
- Secrets appear in git, the container image, Terraform outputs, or logs.
- CI uses long-lived AWS keys or disables TLS verification.
- The repo is harder to run locally than today.

## 5. What the agent is after this change

A general **AWS CloudOps assistant**: it answers questions about the account and gives architecture and troubleshooting help. It is kept as the working baseline and demo surface, and the Spacelift tools are added to it later.

- **Tools:**
  - `use_aws` from `strands-agents-tools`, effectively **read-only**. The runtime IAM role grants only read access (AWS-managed `ReadOnlyAccess` by default; a Terraform variable can swap in a narrower or extra policy), so mutations fail at IAM even if the model tries them.
  - `current_time`.
- **Removed from the agent:**
  - `handoff_to_user` and the text-matching mutation guard, which a read-only role makes unnecessary.
  - `echo_message`.
  - KB tools (moved to legacy).
- **Conversation memory:** AgentCore Memory through the Strands AgentCore memory session manager (the current recommended integration), replacing the hand-rolled context prepending. Memory is enabled when its ID is configured; otherwise the agent runs without memory, for example locally.
- **Serving:** `BedrockAgentCoreApp` (`@app.entrypoint`) with streaming responses, replacing the custom FastAPI app and SSE formatting. Inbound auth is IAM (SigV4) by default. Cognito/JWT and AgentCore Gateway are not used now (moved to legacy); the Spacelift work may bring the Gateway back.
- **System prompt:** rewritten to be concise. It keeps the plan → step-by-step progress style, drops the very long mandatory-emoji rules, and states that the agent is read-only.
- **Conversation management:** keep `SummarizingConversationManager`.
- **Configuration:** environment variables only, set by Terraform on the runtime. A small typed settings module replaces the YAML config manager. Locally, an optional git-ignored `.env` is supported, plus a committed `.env.example`.

## 6. Repository layout

```
src/cloudops_agent/        # package (name: builder's call)
  app.py                   # BedrockAgentCoreApp entrypoint
  agent.py                 # agent factory (model, tools, prompt, memory, conversation manager)
  config.py                # typed settings from env
  tools/                   # local tools; future tool sets (spacelift/, slack/) go here
  prompts.py
tests/                     # pytest unit tests
scripts/                   # local invoke/chat client (IAM-signed InvokeAgentRuntime, or localhost)
infra/                     # Terraform (bootstrap/ + root module + modules/)
Dockerfile                 # arm64, non-root, copies the package (no per-file COPY list)
legacy/                    # moved as-is with git mv, plus a README saying it is unmaintained
docs/                      # current docs; old feature docs move to legacy/docs/
```

The builder decides exactly what moves to legacy, using the list in §2.5 and anything only those pieces use. `docs/ROADMAP.md`, the architecture diagrams, and the pptx stay in `docs/`.

## 7. Libraries and model

- Upgrade to the latest stable `strands-agents`, `strands-agents-tools`, `bedrock-agentcore`, and `boto3`, pinned through `uv.lock`. Drop the many unused direct dependencies in `pyproject.toml` (FastAPI, uvicorn, etc., unless still needed) and `requirements.txt`; `uv` is the single source.
- Python 3.13 (or 3.12 if a dependency requires it), consistent across `.python-version`, the Dockerfile, and CI.
- Model: a Terraform variable. The default is the newest Claude Sonnet-class **inference profile** available in `ap-southeast-1`, checked with `aws bedrock list-inference-profiles`. The builder records the chosen ID.
- Dev tools: `ruff` (lint and format), `pytest`, and optionally `mypy`/`pyright` (builder's call), all as uv dev dependencies.

## 8. Terraform (`infra/`)

- `hashicorp/aws` provider, current 6.x (verified by the builder), using the native `aws_bedrockagentcore_*` resources.
- **`infra/bootstrap/`:** S3 state bucket with versioning, encryption, public access blocked, and TLS-only policy; a GitHub OIDC provider; and a CI deploy role trusted only for this repo's `main` branch and a GitHub `production` environment. This is applied once by an admin with local state, which is documented.
- **`infra/` root module** (S3 backend, `use_lockfile = true`, state key per environment so more environments fit later):
  - ECR repository: immutable tags, scan on push, lifecycle policy.
  - AgentCore Runtime and endpoint: container from ECR with the image tag or digest as a variable, IAM authorizer, environment variables from §5, network mode PUBLIC by default with a variable for VPC later.
  - AgentCore Memory with a short-term-memory event expiry and an optional summarization strategy (builder's call).
  - Runtime execution role:
    - Bedrock invoke on the chosen inference profile and its underlying models only.
    - Memory read/write on that memory only.
    - ECR pull on that repo only.
    - Logs, X-Ray, and CloudWatch metrics scoped to the runtime's log group and namespace.
    - Plus the read-only policy for `use_aws` (§5).
  - CloudWatch log group with retention; runtime observability enabled.
- `variables.tf` has sensible defaults for everything except values that must not have one, such as the image tag. `terraform.tfvars.example` is committed; real tfvars are git-ignored.
- No AWS account IDs or ARNs hard-coded; use data sources and variables.
- The old `modules/` (KB/RAG) Terraform moves to `legacy/`.

## 9. CI/CD (GitHub Actions)

- **On PRs:**
  - `ruff check` and `ruff format --check`, `pytest`.
  - `terraform fmt -check` and `terraform validate`, plus Terraform static analysis (`trivy config` or `checkov`, builder's call).
  - `gitleaks`.
- **On `main`:** build and push the arm64 image to ECR by commit SHA, then `terraform plan` and `apply` in the `production` GitHub environment, which needs a reviewer's approval.
- AWS auth through **OIDC only**. Actions pinned to commit SHAs. Least-privilege `permissions:` per job.
- `runs-on` is configurable and defaults to GitHub-hosted. The open network question (corporate proxy, self-hosted runner) is documented, and none of the old TLS-disabling workarounds are carried over.
- The old `build.yml` and `terraform.yml` move to `legacy/` (not active).

## 10. Security hardening

- Remove from tracked files outside legacy:
  - The Teams webhook URL and Cognito username/client ID in `src/tests/test_lambda_local.py`. These are scrubbed even though the file moves to legacy.
  - The account ID, ARNs, and pool IDs in active config.
  - The `docs/notes.txt` access-portal URL and credential snippets (moved to legacy and scrubbed).
- Add `.gitleaks.toml` (with an allow-list for the known-scrubbed history, if needed), a pre-commit config (gitleaks, ruff, terraform fmt), and a CI scan.
- **README "Security notice":** rotate the leaked Teams webhook. It is still in git history; purging history is the team's decision.
- Container: non-root user, slim base, no build tools in the final image, pinned versions, `.dockerignore` keeps out tests, docs, legacy, and `.env`.
- Logging: no secret values or tokens; drop the "debug_token_validation"-style settings.
- IAM: no `*` actions except where AWS requires them, such as `ecr:GetAuthorizationToken`. Each exception is commented.

## 11. Testing

- Unit tests with no AWS calls (Bedrock and boto3 mocked or stubbed):
  - config parsing and defaults,
  - agent factory wiring (tools, prompt, memory on or off),
  - entrypoint payload handling and streaming output shape,
  - error handling for a bad payload.
- Local smoke test: `uv run` the app on :8080 and call it with the local client script (needs AWS credentials for Bedrock). Also a Docker build and run.
- Terraform: `fmt`, `validate`, and static analysis in CI. A `terraform plan` against the real account is documented, not automated, until the bootstrap is applied.

## 12. Docs

- Rewrite `README.md`:
  - what it is and the architecture (simple diagram),
  - prerequisites,
  - bootstrap and Terraform apply, image build and push,
  - local run and tests,
  - configuration reference,
  - CI setup (OIDC, the `production` environment),
  - security notice,
  - roadmap pointer to the Spacelift spec.
- Update `CLAUDE.md` to the new structure.
- `legacy/README.md`.

## 13. Calls made by Claude (not decided by the user)

- The generic CloudOps chat agent stays as the core and demo baseline (only the KB/RAG, Lambdas, ping monitor, and Cognito/Gateway glue move to legacy). It is effectively read-only through IAM.
- `BedrockAgentCoreApp` replaces FastAPI; IAM inbound auth; no Gateway or Cognito for now.
- AgentCore Memory through the Strands session-manager integration.
- Region `ap-southeast-1`; single environment, laid out so more can be added.
- Bootstrap module for state and OIDC; GitHub-hosted runners by default; `production` environment approval before apply.
- Environment-variable config replaces the YAML config manager.
- No git history rewrite.

## 14. Open items (don't block building)

- Network path and proxy (affects runner choice and runtime network mode). Defaults: GitHub-hosted runners, PUBLIC network mode.
- Hackathon date (affects how much optional hardening is done).
- Spacelift open points: see the parked spec, §11.
