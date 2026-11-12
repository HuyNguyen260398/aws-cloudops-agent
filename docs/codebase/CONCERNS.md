# Codebase Concerns

> Part of the onboarding set. Read this before changing security-relevant code.

## 1) Top Risks (Prioritized)

| Severity | Concern | Evidence | Impact | Suggested action |
|----------|---------|----------|--------|------------------|
| High | Microsoft Teams webhook is still in git history | `.gitleaksignore` (4 fingerprints, one URL); `README.md` security notice | Anyone with repo access can post to that Teams channel | Rotate the webhook. `[ASK USER]` Is it done? |
| Med | `aws_read`'s denylist and redaction cannot be complete; `ReadOnlyAccess` grants broad reads | `src/cloudops_agent/tools/aws_read.py` docstring; `infra/iam.tf` `DenySecretAndDataReads` | A secret under an unrecognized field name could reach the model, memory and traces | Keep IAM as the authority. Consider `ViewOnlyAccess` or a custom read policy through `agent_read_policy_arns`. |
| Med | Log-group creation race | `infra/runtime.tf` (`aws_cloudwatch_log_group.runtime`); runtime role has `logs:CreateLogGroup` (`infra/iam.tf`) | If AgentCore creates the group first, `terraform apply` fails with ResourceAlreadyExists | Drop `CreateLogGroup` from the runtime role, or document `terraform import` |
| Med | No staging environment; `deploy.yml` applies straight to prod after approval | `infra/variables.tf` (`environment = "prod"`), `.github/workflows/deploy.yml` | A bad image goes live | Add a post-deploy smoke test; later, a second environment |
| Low | `deploy.yml` runs on every push to `main`, even before bootstrap and variables are set | `.github/workflows/deploy.yml` | Failing deploy runs until setup is done (nothing is deployed) | Complete the bootstrap steps in `README.md` |
| Low | `actor_id` is not validated against AgentCore's pattern | `src/cloudops_agent/app.py` (`_optional_str`) | A bad value gives a generic error instead of a clear message | Validate with a regex and return a validation message |

## 2) Technical Debt

| Debt item | Why it exists | Where | Risk if ignored | Suggested fix |
|-----------|---------------|-------|-----------------|---------------|
| Default model ID duplicated | Python and Terraform can't share a constant | `src/cloudops_agent/config.py` `DEFAULT_MODEL_ID`, `infra/variables.tf` `model_id` | Local and deployed runs use different models | Add a test that compares the two |
| `tests/test_infra_policies.py` uses regex over HCL | No HCL parser in the dev dependencies | `tests/test_infra_policies.py` | False failures after a reformat | Use `terraform show -json` on a plan, or python-hcl2 |
| Outdated diagrams and deck in `docs/` | Made for the pre-modernization design (Cognito, Gateway, KB) | `docs/aws_agent.drawio*`, `docs/aws-strands-agent.drawio*`, `docs/AWS-CloudOps-Agent.pptx` | Misleads new members | Move them to `legacy/docs/` or update them. `[ASK USER]` |
| `docs/ROADMAP.md` describes features beyond the current scope | Written before the modernization | `docs/ROADMAP.md` | Confusion about what exists | Mark items as planned or done |
| gitleaks version differs between pre-commit (v8.30.0) and CI (v8.30.1) | Pinned separately | `.pre-commit-config.yaml`, `.github/workflows/ci.yml` | Small rule drift | Align them |
| No coverage measurement | Not part of the plan | `pyproject.toml` | Coverage can silently regress | Add pytest-cov and a threshold |

## 3) Security Concerns

| Risk | OWASP category | Evidence | Current mitigation | Gap |
|------|----------------|----------|--------------------|-----|
| Prompt injection through tool output (tags, log lines, resource names) | LLM01 (OWASP LLM Top 10) | `src/cloudops_agent/prompts.py` | The prompt says to treat tool output as data; the agent is read-only; redaction | The model may still be steered into reading and repeating data |
| Leakage of sensitive data to the model, memory or traces | LLM06 / A02 | `aws_read.py`, `infra/iam.tf` | IAM explicit Deny, tool denylist, pattern denylist, redaction | Unknown field names; consider a narrower read policy |
| Deploy pipeline privilege | A01 / supply chain | `infra/bootstrap/main.tf`, `.github/workflows/deploy.yml` | OIDC scoped to the `production` environment; deploy role limited to the runtime role and allowed policies; actions pinned to SHAs | The deploy role can still edit the runtime role's inline policy. The main-only restriction relies on the environment's branch rule. `bedrock-agentcore:*` on the account. |
| Self-hosted runner and fork PRs | Supply chain | `.github/workflows/ci.yml` (`vars.RUNNER`) | Default is GitHub-hosted | If `RUNNER` is self-hosted, fork PR code runs on it. Keep the repo private or require approval for fork PRs. |
| Local runs use the developer's own credentials | A01 | `README.md` | `aws_read` rules still apply | No IAM layer locally; use a read-only profile |

## 4) Performance and Scaling Concerns

| Concern | Evidence | Current symptom | Scaling risk | Suggested improvement |
|---------|----------|-----------------|-------------|-----------------------|
| A new agent and boto3 session are built per request | `app.py` calls `build_agent` per invocation; `aws_read` calls `session_factory()` per tool call | Not measured. `[TODO]` | Added latency per turn | Cache the boto3 session or clients per region if profiling shows a cost |
| Large AWS responses | `MAX_TOOL_OUTPUT_CHARS=20000` truncation | The model sees truncated JSON | Many paginated calls and token cost | The system prompt asks for narrow queries; consider pagination guidance in the tool docstring |
| Summarizing conversation manager calls the model again | `agent.py` (`SummarizingConversationManager`) | Extra Bedrock calls on long sessions | Cost | Tune `summary_ratio` and `preserve_recent_messages` |

## 5) Fragile/High-Churn Areas

| Area | Why fragile | Churn signal | Safe change strategy |
|------|-------------|-------------|----------------------|
| `src/cloudops_agent/tools/aws_read.py` | The security boundary for AWS access | 2 commits in 90 days (scan) | Add tests to `tests/test_aws_read.py` first; never loosen without review |
| `infra/iam.tf`, `infra/bootstrap/main.tf` | Least-privilege IAM; the bootstrap is applied by hand | 2 commits each (scan) | Run `terraform validate`, `trivy`, and `tests/test_infra_policies.py`; re-apply the bootstrap after changing it |
| `src/cloudops_agent/app.py` | Payload contract and error handling | 2 commits (scan) | Keep the five Review Focus behaviours from the plan covered by `tests/test_app.py` |

## 6) `[ASK USER]` Questions

1. [ASK USER] Has the leaked Microsoft Teams webhook been rotated?
2. [ASK USER] Should the old diagrams and deck in `docs/` move to `legacy/docs/`, or be updated to the new architecture?
3. [ASK USER] How should future tools (Spacelift, Slack) get their secrets: AgentCore Identity, Secrets Manager, or env vars?
4. [ASK USER] Is `ReadOnlyAccess` acceptable for the target account, or should the default be `ViewOnlyAccess` or a custom policy?
5. [ASK USER] Should TDD and a coverage threshold be written team rules for hackathon contributions?

## 7) Evidence

- `docs/codebase/.codebase-scan.txt` (HIGH-CHURN FILES, TODO scan: none in production code)
- `src/cloudops_agent/tools/aws_read.py`, `src/cloudops_agent/app.py`, `src/cloudops_agent/agent.py`
- `infra/iam.tf`, `infra/runtime.tf`, `infra/bootstrap/main.tf`
- `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `.gitleaksignore`, `.pre-commit-config.yaml`
