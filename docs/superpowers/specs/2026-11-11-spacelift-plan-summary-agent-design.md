# Spacelift Plan Summary Agent — Design

Date: 2026-11-11
Status: **Parked**. The team will pick this up during the hackathon. It builds on the platform delivered by `2026-11-11-repo-modernization-design.md`. Repo-wide sections here (6.5–6.8) are superseded by that document; the open points are collected in §11.

## 1. Intent

The DevOps team (AWS-focused) is entering a hackathon with the idea of using AI agents in DevOps. The first concrete use case is **pre-deployment plan review for Spacelift**:

> The team deploys infrastructure every **Tuesday**. 30–60 minutes before the deployment window, an AI agent triggers a **plan-only** run on each in-scope Spacelift stack, summarizes the plans with emphasis on significant changes (destroyed resources above all), and posts the summary to the team (Slack) — so the summary is ready when deployment starts.

The agent itself must be the one that triggers the stacks (visible tool calls), not a hidden script — this is the hackathon story.

At the same time, the repo has not been maintained for a while. This work brings it up to current AWS / Bedrock AgentCore / Strands Agents practice, provisions all agent infrastructure with Terraform, and hardens security, so the repo is ready to build on during the hackathon.

## 2. Goals

1. **Spacelift plan summary feature**, agent-driven:
   - Weekly scheduled run (configurable lead time before the Tuesday window), plus an on-demand trigger for live demos.
   - Agent triggers **PROPOSED** (plan-only) runs on the configured stacks via Spacelift tools, waits for them, reads the changes, writes the summary.
   - Report delivered to Slack via **either** an incoming webhook **or** a Slack bot app (chosen by configuration); both implemented.
2. **Modernize** the agent on current Strands Agents SDK, `bedrock-agentcore` SDK, and a current Claude model on Bedrock.
3. **Terraform** provisions all AWS infrastructure for the agent (replacing `src/ops/deploy_*.py` and hand-maintained ARNs in `config/dynamic-config.yaml`).
4. **Security hardening**: plan-only enforced at multiple layers, least-privilege IAM, no secrets in the repo, secure CI.
5. **Move unrelated code to `legacy/`** so the repo centers on the new agent.

## 3. Non-goals

- Deciding the final "significant change" rules beyond a sensible default (team will refine later; destroyed resources are the top concern).
- Selecting the final set of stacks (≈50 exist; selection is configuration, decided later).
- Choosing between Slack webhook and Slack bot (team decides before the hackathon; both supported).
- Any change to how deployments are approved/applied in Spacelift.
- Maintaining or modernizing the legacy features (ping monitor, approval/remediation Lambdas, KB/RAG, generic AWS chat).
- Adopting the managed **AWS DevOps Agent** service (evaluated, see §9; possible later integration).

## 4. Anti-goals (failure even if it "works")

- The agent can **confirm, apply, or discard** a Spacelift run, or trigger a TRACKED run. Plan-only must hold even if the model misbehaves or is prompt-injected via plan output.
- Stacks silently missing from the report (a stack in scope that isn't triggered or reported must be called out explicitly).
- Secrets (Spacelift API key, Slack token/webhook) in git, container images, Terraform state outputs, or logs.
- Long-lived AWS access keys in CI.
- A summary that buries destroyed resources or presents a failed plan as "no changes".

## 5. Current state (what exists)

- `src/agent_runtime.py`: FastAPI app on :8080 (`/invocations`, `/ping`) run on AgentCore Runtime; Strands agent with `use_aws`, `handoff_to_user`, KB tools; optional AgentCore Gateway (MCP, Cognito M2M token) and AgentCore Memory.
- Pinned `bedrock-agentcore<=0.1.5`, `bedrock-agentcore-starter-toolkit==0.1.14`, unpinned `strands-agents`. Model `global.anthropic.claude-haiku-4-5-20251001-v1:0`.
- Deployment via Python scripts (`src/ops/deploy_runtime.py`, `deploy_memory.py`) writing ARNs to `config/dynamic-config.yaml`; image built/pushed by hand.
- Terraform in `modules/` only covers the KB/RAG stack; CI (`.github/workflows/terraform.yml`) uses static AWS keys, disables TLS verification, runs on `feature/pipeline`.
- `dockerfile` hand-copies individual files from `src/`.
- Security issues found:
  - `src/tests/test_lambda_local.py` contains a live-looking Microsoft Teams webhook URL (with key), a Cognito username/client ID, account ARNs. **Webhook must be rotated by the team** (it remains in git history).
  - AWS account ID and Cognito pool/client IDs in `config/*.yaml`, `assets/policies/*.json`, `docs/notes.txt`.
  - CI disables TLS verification (`NODE_TLS_REJECT_UNAUTHORIZED=0`, `git config http.sslVerify false`) and uses long-lived access keys.
  - Runtime role allows broad `use_aws` (any AWS API the role permits); mutation guard is a text match on tool output.
  - `python-dotenv` used but not declared.

## 6. Design

### 6.1 Repository layout after the change

```
legacy/                      # moved as-is, not built/tested/deployed; README explains
  src/lambdas/, src/tools/kb_retrieval.py, src/components/{gateway,mcp,auth,memory}.py*,
  cloudformation/, modules/ (KB/RAG terraform), assets/, scripts/, src/ops/, src/tests/,
  docs/ (feature docs for legacy pieces), config/*.yaml (old)
src/plan_agent/              # new agent package (name is builder's call)
infra/                       # Terraform for the agent (root module + modules)
.github/workflows/           # rewritten CI
docs/                        # current docs; specs under docs/superpowers/specs/
```

\* Components reused by the new agent are copied/rewritten into the new package rather than imported from `legacy/`. Exactly what is reused is the builder's call.

Git history is preserved (`git mv`). The `.github/workflows/terraform.yml` for KB/RAG moves to `legacy/` (disabled).

### 6.2 Runtime architecture

```
EventBridge Scheduler (cron, Tuesday, lead time configurable, timezone configurable)
   └─> Lambda "trigger" (IAM-auth InvokeAgentRuntime, payload {"mode":"weekly_plan"})
          └─> AgentCore Runtime (container, arm64)
                 entrypoint returns immediately; work continues as an async/background task
                 Strands Agent
                   ├─ Spacelift tools (via spacectl MCP server, stdio subprocess in the container) — allow-listed
                   ├─ wait_for_runs (custom tool, code-side polling)
                   ├─ get_run_changes (custom tool, compact structured change list)  [if MCP lacks it]
                   └─ publish_report (custom tool → Slack webhook or Slack bot)
                 coverage check in code after the agent finishes
On-demand: CLI script / Slack (if bot) → same runtime, same mode, or free-form chat mode
```

Key decisions (from the conversation):

- **The agent triggers each stack itself** through Spacelift tools (user requirement).
- **Polling is code, not tokens**: a `wait_for_runs(run_ids, timeout)` tool blocks and polls Spacelift until all runs reach a terminal plan state (e.g. `UNCONFIRMED`, `FINISHED`, `FAILED`, `DISCARDED`, `CANCELED` — exact states verified by builder), returning a compact status per run.
- **Concurrency**: the agent works in batches (default 10 stacks per batch, configurable) to respect Spacelift worker capacity and stay inside the lead time for ~50 stacks.
- **Coverage guarantee in code**: after the agent finishes, code compares the configured stack list against stacks actually triggered/reported; any gaps are appended to the report as "NOT PLANNED" and the run is marked degraded.
- **Long-running**: weekly run of ~50 plans can exceed typical request timeouts; use the AgentCore Runtime async/background-task pattern (`bedrock-agentcore` SDK) so `/ping` reports busy while work continues. The trigger Lambda does not wait.
- The existing FastAPI wrapper is replaced by the `bedrock-agentcore` SDK app (`BedrockAgentCoreApp`) unless the builder finds a reason to keep FastAPI.

### 6.3 Spacelift integration

- Use the **official `spacectl` MCP server** (`spacectl mcp server`), bundled in the container image (pinned version, checksum verified), spawned as a stdio MCP subprocess via Strands `MCPClient`.
- Auth via Spacelift API key: `SPACELIFT_API_KEY_ENDPOINT`, `SPACELIFT_API_KEY_ID`, `SPACELIFT_API_KEY_SECRET`, loaded at startup from **AWS Secrets Manager** (never env-baked into the image or Terraform outputs).
- **Tool allow-list** passed to the agent: read/discovery tools + `trigger_stack_run`. **Excluded**: `confirm_stack_run`, `discard_stack_run`, and any other mutating tool. `trigger_stack_run` is wrapped so it can only create **PROPOSED** runs (wrapper forces/validates run type; TRACKED requests are rejected).
- Spacelift-side least privilege: the API key's role/space permissions should allow triggering proposed runs and reading runs, not confirming/applying. The exact Spacelift permission set is to be verified by the builder against Spacelift docs and documented in the README as a setup step for the team.
- If the MCP server cannot return plan changes in a usable form, add a small GraphQL client tool (`get_run_changes`) using the same API key (read-only query).
- Stack selection config: either a Spacelift **label** (default, e.g. `weekly-plan-review`) or an explicit list of stack IDs, or a space ID — configurable via Terraform variable → runtime env var. Default label is the builder's call; must be documented.

### 6.4 Summary content (default; team refines later)

Report sections, in order:

1. Header: run time, number of stacks planned / with changes / failed / not planned, link to each Spacelift run.
2. **Destroyed resources** (top priority) — per stack, resource addresses.
3. Replaced resources (delete+create).
4. Failed plans (blocking).
5. Stacks with other changes (added/changed counts, notable items as judged by the model).
6. Stacks with no changes (compact list).
7. Stacks not planned (coverage gaps).

The model writes the narrative and the "notable items" judgment; counts and the destroyed/replaced/failed/no-change classification come from structured data, not model inference, so they can't be hallucinated.

Delivery:

- **Webhook mode**: one message (Block Kit), truncated sensibly with a note when too long.
- **Bot mode** (`chat.postMessage` with bot token): top-level summary message + per-stack details as thread replies.
- Mode selected by config; secrets in Secrets Manager.
- Report also written to CloudWatch Logs (structured) for audit.

### 6.5 Models and libraries

- Upgrade to latest stable `strands-agents`, `strands-agents-tools` (only if still needed), `bedrock-agentcore`, `boto3`, `mcp`; pin via `uv.lock`. Remove `bedrock-agentcore-starter-toolkit` from runtime deps (dev-only if kept). Remove unused dependencies. Declare everything used (e.g. `python-dotenv` only if used).
- Model: a current Claude model available on Bedrock in the deployment region via inference profile; model ID is a Terraform variable. The builder picks the default by checking availability (`aws bedrock list-inference-profiles`) — prefer the latest Sonnet-class model for summarization quality.
- Python version: 3.12 or 3.13 (builder's call, consistent across container, CI, `.python-version`).

### 6.6 Terraform (`infra/`)

- Provider: `hashicorp/aws` recent 6.x (version verified by builder) using native `aws_bedrockagentcore_*` resources.
- Remote state: S3 backend with native lockfile (`use_lockfile = true`); bootstrap of the state bucket documented (small separate bootstrap config or documented manual step — builder's call).
- Resources (minimum):
  - ECR repository (immutable tags, scan on push, lifecycle policy).
  - AgentCore Runtime + endpoint (container artifact from ECR, IAM authorizer, env vars for non-secret config, secret ARNs).
  - Runtime execution role: Bedrock `InvokeModel*` on the chosen model/inference profile only; read the specific secrets; logs/X-Ray/metrics for its own log group; ECR pull on its own repo. **No `use_aws`-style broad AWS access** (the new agent doesn't need AWS APIs beyond these).
  - Secrets Manager secrets (Spacelift API key, Slack webhook URL / bot token) — Terraform creates the secret containers; values are set out-of-band (CLI/console), never in tfvars committed to git.
  - KMS: AWS-managed keys acceptable; customer-managed key is the builder's call.
  - Trigger Lambda + role (invoke only this runtime).
  - EventBridge Scheduler schedule (cron + timezone variables) + role.
  - CloudWatch log groups with retention; observability enabled on the runtime.
- AgentCore Memory and Gateway are **not required** for this feature; don't provision them unless the builder finds a concrete need.
- Image build/push is done by CI (or a documented `make`/script); Terraform consumes the image tag/digest as a variable.

### 6.7 CI/CD (GitHub Actions)

- Auth to AWS via **GitHub OIDC** role (provisioned by Terraform, scoped to this repo/branch) — no static keys.
- PR: lint (ruff), type check optional, unit tests (pytest), `terraform fmt -check`, `terraform validate`, `tflint`/`checkov` or `trivy config` (builder's call), secret scan (gitleaks), `terraform plan` (optional if creds available).
- Main: build & push arm64 image, `terraform apply` (manual approval via GitHub environment).
- Pin third-party actions to commit SHAs. Remove TLS-disabling settings.
- Runner: GitHub-hosted by default; the old self-hosted runner/proxy workarounds are not carried over (team can re-add if their network requires it).

### 6.8 Security hardening checklist

- Remove the Teams webhook, Cognito username, and other credentials from tracked files; add a **gitleaks** config + pre-commit hook + CI step. Document in the README that the leaked Teams webhook must be **rotated** (git history still contains it; history rewrite is a team decision, not done here).
- Replace hard-coded account ID / ARNs in active code and config with Terraform variables/data sources. (Legacy files keep their content but are not deployed.)
- Plan-only enforced at 3 layers: tool allow-list + PROPOSED-only wrapper (code), Spacelift API key permissions (Spacelift), and prompt instruction (model). Optionally AgentCore Policy if tools are moved behind AgentCore Gateway (builder's call; not required).
- Treat plan output as untrusted input: system prompt instructs the model to never follow instructions found in plan output; tool layer guarantees it can't act on them anyway.
- Least-privilege IAM for every role; no wildcards on actions where avoidable.
- Container: non-root user, minimal base image, pinned versions, no secrets in image.
- Logs must not include secret values (redaction in logger for known secret keys).

### 6.9 Testing

- Unit tests (pytest) for: stack selection, PROPOSED-only wrapper (rejects TRACKED/confirm/discard), `wait_for_runs` polling/timeout logic (mocked Spacelift), change classification (destroyed/replaced/failed/no-change), coverage check, Slack payload builders (webhook vs bot, truncation).
- A fake Spacelift fixture (recorded/mock responses) so the full weekly flow can be run locally without Spacelift.
- Local run: container on :8080 with mock or real Spacelift; on-demand CLI to trigger the weekly mode.
- Terraform: `fmt`, `validate`, static analysis in CI.

### 6.10 Docs

- Rewrite `README.md`: what it does, architecture diagram (simple), setup (Spacelift API key + permissions, Slack webhook or bot app, Secrets Manager values, Terraform bootstrap/apply, CI OIDC), how to run locally and on-demand, configuration reference.
- `legacy/README.md`: what's there and that it's unmaintained.
- Update `CLAUDE.md` to the new structure.
- Rotation notice for the leaked Teams webhook.

## 7. Configuration reference (all via Terraform variables → runtime env / secrets)

| Setting | Default (builder may adjust) |
|---|---|
| AWS region | `ap-southeast-1` |
| Model ID | latest available Claude Sonnet-class inference profile in region |
| Schedule | Tuesday, time + timezone variables (defaults: team to set; placeholder 09:00 `Asia/Ho_Chi_Minh`) |
| Lead time | 60 minutes |
| Stack selection | label `weekly-plan-review` (or list of stack IDs / space ID) |
| Batch size | 10 |
| Plan wait timeout | 45 minutes |
| Slack mode | `webhook` or `bot` |
| Slack channel (bot mode) | variable |

## 8. Calls made by Claude (not explicitly decided by the user)

- Region stays `ap-southeast-1`.
- Spacelift via official `spacectl` MCP server bundled as stdio subprocess; GraphQL fallback for change details.
- Code-side `wait_for_runs` polling + code-side coverage check + structured classification; model writes narrative.
- EventBridge Scheduler → Lambda → AgentCore Runtime (async task).
- AgentCore Memory/Gateway/Cognito not used by the new agent.
- Secrets in AWS Secrets Manager; S3 backend with lockfile; GitHub OIDC; GitHub-hosted runners.
- Legacy code moved with `git mv`, not refactored.
- No git history rewrite for the leaked webhook (rotation recommended instead).

## 9. AWS DevOps Agent vs. AgentCore (evaluation summary)

AWS DevOps Agent is a managed agent focused on incident investigation (alarm → root cause → mitigation plan executed by humans), billed per agent-second (~$30/agent-hour after a 2-month trial). It can use custom MCP servers, but they must be remote Streamable-HTTP servers, so `spacectl` would still need hosting (e.g. on AgentCore). For a scheduled pre-deployment plan review that triggers Spacelift runs and posts a custom report, AgentCore + Strands fits better (full control of tools/guardrails, pay-per-use, and the team builds the solution — a better hackathon story). Possible later: expose the Spacelift tooling to AWS DevOps Agent as a custom MCP server.

## 10. Open items for the team (do not block building)

- Final stack selection (label/list), schedule time and timezone.
- Slack webhook vs bot app.
- Spacelift API key creation with plan-only permissions.
- Rotating the leaked Teams webhook; whether to purge git history.
- Refining "significant change" rules.

## 11. Open points to resolve at the hackathon

Ranked by how much the answer changes what gets built.

1. **What code the Tuesday plan runs against.** A proposed run triggered through the API without a commit plans the latest commit of the stack's tracked branch. That is only right if Tuesday deploys exactly that commit. If changes sit in PRs merged on Tuesday, or deploys come from a release branch or tag, the report would mostly show drift. This decides whether the trigger takes a commit, branch, or PR per stack, and what "stale plan" means.
2. **Network path.** Can AgentCore Runtime (and the trigger Lambda) reach Spacelift (`*.app.spacelift.io`, or is Spacelift self-hosted?) and Slack over the public internet, or is there a TLS-intercepting corporate proxy? This decides public vs. VPC network mode, NAT/endpoints, and a custom CA bundle in the image.
3. **Stack selection.** Which of the ~50 stacks: a label, an explicit list, or a space.
4. **Schedule.** Exact Tuesday deploy time, time zone, and lead time (30 or 60 minutes).
5. **Slack delivery.** Incoming webhook or bot app (both will be supported; pick one to configure), and the target channel.
6. **Spacelift API key.** Create a key whose role can trigger proposed runs and read runs, but cannot confirm, apply, or discard. Verify the exact Spacelift permission set.
7. **Stack types and dependencies.** Are all in-scope stacks Terraform/OpenTofu? Do any depend on each other (stack dependencies or output references)? This affects the change parser, batch ordering, and the "plan may be inaccurate until upstream applies" caveat.
8. **"Significant change" rules.** Destroyed resources are the top concern. Refine what else gets flagged (replacements, IAM, security groups, stateful resources).
9. **On-demand trigger.** CLI only (default), or also from Slack, which needs a public endpoint and Slack signing-secret verification.
10. **Plan-only enforcement.** Confirm the `spacectl` MCP server version, its exact tool names and arguments, and whether it returns plan changes, or whether a GraphQL fallback tool is needed.
