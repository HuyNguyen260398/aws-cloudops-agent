# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

An AWS CloudOps assistant built on the Strands Agents SDK and Amazon Bedrock, deployed as a container on **Amazon Bedrock AgentCore Runtime**. Around it are AWS Lambdas that watch services (such as domain pings), ask the agent to analyze an incident, and run the remediation it suggests once a human approves it in Slack or Teams. There is also Terraform for a Bedrock Knowledge Base (RAG). Python 3.11, managed with `uv`. Primary region is `ap-southeast-1`; the Knowledge Base is in `ap-southeast-2`.

## Commands

```bash
uv sync                                         # install deps

# Run the agent server locally (FastAPI on :8080, POST /invocations streams SSE, GET /ping)
uv run python src/agent_runtime.py
curl -N -X POST http://localhost:8080/invocations -H "Content-Type: application/json" \
  -d '{"prompt": "List my S3 buckets", "session_id": "test-session-123456789012345678901"}'

# Run it as a container (same image AgentCore runs; arm64)
docker build -t aws-cloudops-agent -f dockerfile .
docker run -p 8080:8080 -v ~/.aws:/root/.aws aws-cloudops-agent

# Interactive client against local (no auth) or the deployed runtime (Cognito JWT)
uv run python src/ops/agent_client.py --local
uv run python src/ops/agent_client.py
uv run python src/ops/invoke_agent.py           # boto3 bedrock-agentcore invoke of runtime.p_agent.arn

# Deploy (the image must already be pushed to the ECR URI in dynamic-config.yaml)
uv run python src/ops/deploy_memory.py
uv run python src/ops/deploy_runtime.py

# Knowledge Base infrastructure
terraform -chdir=modules init && terraform -chdir=modules apply
```

There is no pytest suite, linter, or formatter. The files in `src/tests/` are standalone scripts (`uv run python src/tests/test_kb_retrieval.py`). Most of them call real AWS resources, and `test_lambda_local.py` sets environment variables for real endpoints.

The README is out of date. It refers to `src/agent_cli.py`, `src/agent_streaming.py`, `deploy.ps1` and several `*_GUIDE.md` files, none of which exist. Use the commands above, `docs/DEPLOYMENT_COMMANDS.md`, and the other `docs/*.md` guides instead.

## Architecture

### Agent runtime (`src/agent_runtime.py`)

This is the container entry point and the only code AgentCore runs. Each `/invocations` request goes through these steps:

1. If AgentCore Memory is available and a `session_id` is given, `components/memory.py` fetches recent turns and prepends them to the prompt.
2. `execute_agent_streaming()` builds the tool list:
   - **Gateway path:** if `gateway.url` is configured and a Cognito token was obtained at startup (`components/auth.py`, which needs the `COGNITO_USERNAME`, `COGNITO_PASSWORD` and `COGNITO_CLIENT_ID` env vars), it opens an MCP client to the AgentCore Gateway. It then runs a semantic `tool_search` (`components/gateway.py`) with keywords from `utils/query_extractor.py` and adds the top 10 MCP tools to the local tools.
   - **Fallback:** if there is no gateway or token, or anything throws, only local tools are used: `use_aws`, `handoff_to_user`, `get_current_time`, `echo_message`, and `tools/kb_retrieval.py`.
3. Strands events are turned into SSE `data:` lines by `utils/responses.py:format_diy_response`. A `handoff_to_user` tool call, or the "is potentially mutative" confirmation text from `use_aws`, stops the stream and sends a `handoff_required` event, so the client has to send a yes/no follow-up.
4. The full response text is saved back to memory.

`agents/aws_cloudops_agent.py` subclasses Strands `Agent`. It holds the long system prompt, which requires 🔍/✅ progress updates around every tool call and confirmation before mutations, and it uses `components/conversation_manager.py` (a `SummarizingConversationManager`).

### Configuration

`utils/config_manager.py:AgentCoreConfigManager` finds the project root by walking up to `.agentcore.yaml`, then deep-merges two files:

- `config/static-config.yaml`: edited by hand. It holds the region, Bedrock `agents.modelid`, Cognito pool and client IDs, gateway URL, Knowledge Base ID, and the `tools_schema` used to create gateway targets.
- `config/dynamic-config.yaml`: written by the deploy scripts through `update_dynamic_config()`. It holds runtime, memory and gateway ARNs and the ECR URI.

Secrets are loaded from `config/.env` (gitignored) with `python-dotenv`. `tools/kb_retrieval.py` reads `KNOWLEDGE_BASE_ID` and `BEDROCK_REGION` from the environment, not from the YAML. `components/memory.py` uses the older `utils/config.py:load_configs()` rather than the config manager.

### Imports and the Docker image

Modules inside `src/` import each other as top-level packages (`from utils.config_manager import ...`, `from components.auth import ...`), so `src/` has to be on `sys.path`. Scripts under `src/ops/` and `src/tests/` add it themselves.

The `dockerfile` copies a hand-picked list of files from `src/` flat into `/app` (`/app/utils/`, `/app/agents/`, `/app/components/`, `/app/tools/`, `/app/agent_runtime.py`). **When you add a module the runtime imports, you must also add a `COPY` line for it**, or the container will fail at import time. The last `CMD` decides whether the image runs locally (uvicorn) or under AgentCore (`opentelemetry-instrument`); switch between them by swapping which line is commented out.

### Event-driven ops (`src/lambdas/`, `cloudformation/`, `scripts/`)

These Lambdas are deployed separately with CloudFormation templates and PowerShell scripts, not as part of the runtime image:

- `lambda_ping_monitor.py` / `lambda_invoke_handler.py`: detect a service issue, call the deployed runtime over HTTPS with a Cognito JWT (using `urllib`), and post the analysis to SNS, Teams or Slack.
- `lambda_approval_handler.py`: checks the Slack signature, records the approval in DynamoDB (alerts expire via TTL), and triggers execution.
- `lambda_execution_handler.py`: asks the agent to carry out the approved remediation.

The `*_copy.py` files are older variants. See `docs/LAMBDA_PING_MONITOR.md` and `docs/FEATURE_SLACK_APPROVAL.md`.

### RAG infrastructure (`modules/`, `assets/ingest_lambda/`)

Terraform creates an S3 documents bucket, an OpenSearch Serverless collection, a Bedrock Knowledge Base (Titan Embed v2, `ap-southeast-2`), and an ingest Lambda that S3 uploads trigger. `.github/workflows/terraform.yml` applies it from a self-hosted runner, keeping state in S3. It currently triggers only on `feature/pipeline` or manual dispatch.
