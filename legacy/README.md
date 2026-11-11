# legacy/

The pre-2026-11 version of this repo, moved here with `git mv` so its history is kept.

It contains:
- the domain ping monitor and the Slack/Teams approval and remediation Lambdas (`src/lambdas/`, `cloudformation/`, `scripts/`)
- the Bedrock Knowledge Base / RAG Terraform (`modules/`, `assets/ingest_lambda/`)
- the Cognito JWT and AgentCore Gateway glue, and the old FastAPI runtime (`src/agent_runtime.py`, `src/components/`, `config/`)
- the old CI workflows (`.github/workflows/`) and feature docs (`docs/`)

**This code is unmaintained.** It is not built, tested, linted, or deployed, and its workflows do not run.

> **Security notice:** a Microsoft Teams incoming-webhook URL was previously committed in
> `src/tests/test_lambda_local.py`. It has been scrubbed from the working tree but **remains in
> git history — rotate (delete and recreate) that webhook.** AWS account IDs in these files were replaced with `<ACCOUNT_ID>`.
