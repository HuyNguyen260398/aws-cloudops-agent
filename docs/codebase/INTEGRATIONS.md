# External Integrations

> Part of the onboarding set. The AWS architecture diagram is in [../ONBOARDING.md §5](../ONBOARDING.md#5-aws-architecture)
> and [../diagrams/aws-architecture.drawio](../diagrams/aws-architecture.drawio).

## 1) Integration Inventory

### Runtime: what the agent itself calls

| System | Type | Purpose | Auth model | Criticality | Evidence |
|--------|------|---------|------------|-------------|----------|
| Amazon Bedrock (`global.anthropic.claude-sonnet-5-5` inference profile) | Model API (`InvokeModelWithResponseStream`) | The LLM | Runtime IAM role. Allowed only on that inference profile, and on foundation models only *through* it (`bedrock:InferenceProfileArn` condition). | High | `src/cloudops_agent/agent.py`, `infra/iam.tf` |
| AWS service APIs (EC2, S3, CloudWatch, Logs, Lambda, …) | boto3, via the `aws_read` tool | Live account facts | Runtime IAM role with `ReadOnlyAccess` (configurable `agent_read_policy_arns`) plus an explicit Deny on secret and data reads | High | `src/cloudops_agent/tools/aws_read.py`, `infra/iam.tf` |
| AgentCore Memory (`cloudops_agent_memory`) | Managed event store | Conversation history per `actor_id`/`session_id` | Runtime role: `CreateEvent`, `ListEvents`, `GetEvent`, `DeleteEvent` and others, on this memory only | Medium (optional; off without `MEMORY_ID`) | `src/cloudops_agent/agent.py`, `infra/memory.tf`, `infra/iam.tf` |
| AgentCore Runtime | Host | Runs the container. Callers use `InvokeAgentRuntime` (endpoint qualifier `cloudops_agent_live`). | **Inbound:** IAM SigV4, because no `authorizer_configuration` is set. **Outbound:** the runtime assumes `cloudops-agent-runtime`. | High | `infra/runtime.tf` |
| CloudWatch Logs, X-Ray, CloudWatch metrics | Observability | Container stdout logs; OpenTelemetry traces and metrics | Runtime role. Logs are scoped to `/aws/bedrock-agentcore/runtimes/*`, metrics to the `bedrock-agentcore` namespace, and X-Ray uses `*` because AWS requires it. | Medium | `infra/iam.tf`, `infra/runtime.tf`, `Dockerfile` CMD |
| Amazon ECR (`cloudops-agent`) | Image registry | Image source for the runtime | Runtime role (pull), deploy role (push) | High (deploy) | `infra/bootstrap/main.tf`, `infra/iam.tf` |

### Delivery: CI/CD and state

| System | Type | Purpose | Auth model | Evidence |
|--------|------|---------|------------|----------|
| GitHub Actions → AWS STS | OIDC federation | Deploy without static keys | `sts:AssumeRoleWithWebIdentity`. `sub` must equal `repo:<owner/name>:environment:production`, and `aud` must equal `sts.amazonaws.com`. | `infra/bootstrap/main.tf`, `.github/workflows/deploy.yml` |
| S3 state bucket | Terraform backend | `cloudops-agent/prod.tfstate` with S3 native locking (`use_lockfile`) | Deploy role (object read/write/delete plus ListBucket) | `infra/bootstrap/main.tf`, `infra/backend.hcl.example` |
| Third-party GitHub Actions | CI | checkout, setup-uv, setup-terraform, configure-aws-credentials, ecr-login, buildx/qemu/build-push, trivy-action | Pinned by commit SHA | `.github/workflows/*.yml` |
| Container images | Build | `ghcr.io/astral-sh/uv`, `python:3.13-slim-bookworm`, `zricethezav/gitleaks` | Pinned by digest | `Dockerfile`, `ci.yml` |

**Not integrated (moved to `legacy/`):** Cognito/JWT, AgentCore Gateway (MCP), Bedrock
Knowledge Base/OpenSearch, Slack/Teams webhooks, SNS, DynamoDB, and the ping-monitor
Lambdas. The parked Spacelift spec may bring the Gateway and Slack back
(Spacelift plan-summary agent design spec, kept outside the repo).

## 2) Data Stores

| Store | Role | Access layer | Key risk | Evidence |
|-------|------|--------------|----------|----------|
| AgentCore Memory | Short-term conversation events. Expire after `memory_event_expiry_days` (30). No long-term strategies. | `AgentCoreMemorySessionManager` in `agent.py` | Conversation text, including tool output, is stored for 30 days. Redaction in `aws_read` limits the secrets that reach it. | `infra/memory.tf`, `src/cloudops_agent/agent.py` |
| S3 state bucket | Terraform state | Terraform backend | State holds resource IDs and ARNs. It is protected by versioning, KMS, TLS-only access, a public-access block and `prevent_destroy`. | `infra/bootstrap/main.tf` |
| Local `infra/bootstrap/terraform.tfstate` | Bootstrap state | Admin's machine | If it is lost, bootstrap resources must be imported back. It is git-ignored (`*.tfstate*`). | `infra/bootstrap/versions.tf`, `.gitignore` |

## 3) Secrets and Credentials Handling

- **Credential sources:**
  - At runtime, the AgentCore execution role provides credentials automatically. There are no
    keys in the image or in env.
  - Locally, your AWS profile or SSO.
  - In CI, a GitHub OIDC token exchanged for short-lived STS credentials.
- **Hard-coding checks:**
  - gitleaks runs in CI over the full history and in pre-commit. `.gitleaksignore` contains
    only the fingerprints of one historical Teams webhook, which must be rotated.
  - `.env`, `*.tfvars` and `backend.hcl` are git-ignored.
- **Rotation:** **the Microsoft Teams webhook in git history must be rotated** (`README.md`
  security notice). `[ASK USER]` Has it been rotated yet?
- **App secrets for future tools** (Spacelift and Slack tokens): there is no mechanism yet.
  `[ASK USER]` Should they come from AgentCore Identity, Secrets Manager, or runtime env vars?

## 4) Reliability and Failure Behavior

- **Retry/backoff:**
  - Strands' default `ModelRetryStrategy` retries model calls on throttling: 6 attempts, 4 s
    initial delay, 240 s maximum (`strands/agent/agent.py`, using the default because
    `build_agent` passes none).
  - boto3 calls in `aws_read` use botocore's default retry mode. There is no custom
    configuration.
- **Timeouts:**
  - `scripts/invoke.py` uses `read_timeout=300` for the boto3 client and `timeout=300` for the
    local `urlopen`.
  - The server sets no tool-call timeout. `[TODO]` decide whether long `aws_read` calls need
    one.
- **Fallbacks:**
  - Tool errors come back to the model as strings (`AWS error <Code>: …`), so it can explain
    AccessDenied and similar errors.
  - Any unexpected exception ends the stream with a generic error line.
  - Without `MEMORY_ID` or a session ID, the agent runs without memory.

## 5) Observability for Integrations

- **Logging:**
  - JSON lines on stdout go to CloudWatch Logs.
  - `aws_read` logs `BotoCoreError` as a warning.
  - `app.py` logs a full stack trace for each failed invocation, including the session ID.
- **Metrics and tracing:** `opentelemetry-instrument` (aws-opentelemetry-distro) in the
  container CMD sends traces to X-Ray and metrics to CloudWatch (`bedrock-agentcore`
  namespace). Strands emits GenAI spans.
- **Gaps:**
  - There are no custom metrics, such as tool refusals or truncations.
  - No dashboards or alarms are defined in Terraform. `[TODO]`
  - The runtime's observability (Transaction Search / GenAI dashboard) setup is not in
    Terraform. `[TODO]` verify the account-level CloudWatch settings.

## 6) Evidence

- `src/cloudops_agent/agent.py`, `src/cloudops_agent/tools/aws_read.py`, `scripts/invoke.py`
- `infra/iam.tf`, `infra/runtime.tf`, `infra/memory.tf`, `infra/bootstrap/main.tf`
- `.github/workflows/deploy.yml`, `.gitleaksignore`, `.env.example`, `Dockerfile`
