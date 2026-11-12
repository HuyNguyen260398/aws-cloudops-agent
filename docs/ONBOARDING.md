# Onboarding: AWS CloudOps Agent

Welcome. Start here. This page walks you through the system with diagrams. The detailed
reference docs are in [`docs/codebase/`](codebase/).

| If you want to… | Read |
|---|---|
| See which languages, libraries, and tools we use | [codebase/STACK.md](codebase/STACK.md) |
| Find your way around the folders | [codebase/STRUCTURE.md](codebase/STRUCTURE.md) |
| Understand how a request flows and why the design is this way | [codebase/ARCHITECTURE.md](codebase/ARCHITECTURE.md) |
| Write code that matches ours (style, errors, logging) | [codebase/CONVENTIONS.md](codebase/CONVENTIONS.md) |
| Know which AWS services and external systems we touch | [codebase/INTEGRATIONS.md](codebase/INTEGRATIONS.md) |
| Run and write tests | [codebase/TESTING.md](codebase/TESTING.md) |
| Know the risks and sharp edges before you change things | [codebase/CONCERNS.md](codebase/CONCERNS.md) |
| Deploy or configure the agent | [../README.md](../README.md) |
| Look at the AWS architecture diagram with official icons | [diagrams/aws-architecture.drawio](diagrams/aws-architecture.drawio) (open it in [draw.io](https://app.diagrams.net) or the VS Code Draw.io extension) |

---

## 1. What this repo is (in 30 seconds)

- It is a **chat agent for AWS operations**. You ask it things like "why is my Lambda failing?"
  or "how many S3 buckets do I have?". It calls AWS APIs **read-only** and answers in a
  streamed reply.
- It is built with the **Strands Agents** SDK and uses **Claude Sonnet on Amazon Bedrock** as
  its model.
- It runs as an **arm64 container on Amazon Bedrock AgentCore Runtime**. That is a serverless
  host for agents: AWS starts the container on demand, and callers must sign their requests
  with IAM.
- **Terraform** creates every AWS resource, and **GitHub Actions** deploys it from `main` after a
  reviewer approves.
- It is the **base for the team's AI-agents hackathon**. New tool sets, such as Spacelift and
  Slack, plug into `src/cloudops_agent/tools/`.
- Everything under `legacy/` is the old, unmaintained version. It is kept for reference only.

---

## 2. Component diagram (inside the container)

```mermaid
flowchart TB
    subgraph container["Container: python -m cloudops_agent.app (port 8080, uid 1000)"]
        direction TB
        sdk["BedrockAgentCoreApp<br/><i>bedrock-agentcore SDK</i><br/>POST /invocations · GET /ping · SSE"]
        app["app.py<br/>invoke(payload, context)<br/>validate → stream text"]
        cfg["config.py<br/>load_settings() → Settings"]
        log["logging_setup.py<br/>JSON lines to stdout"]
        agentf["agent.py<br/>build_agent(settings, session_id, actor_id)"]
        prompt["prompts.py<br/>SYSTEM_PROMPT (read-only rules)"]
        tool["tools/aws_read.py<br/>make_aws_read_tool(settings)"]

        subgraph strands["Strands Agent (one per request)"]
            model["BedrockModel<br/>(streaming)"]
            conv["SummarizingConversationManager"]
            time["ContextInjector<br/>current UTC time"]
            sm["AgentCoreMemorySessionManager<br/>(only if MEMORY_ID and a session id)"]
        end
    end

    sdk --> app
    app --> cfg
    app --> log
    app --> agentf
    agentf --> prompt
    agentf --> tool
    agentf --> strands
    tool -->|"boto3 (read-only)"| awsapis[("AWS service APIs")]
    model -->|"InvokeModelWithResponseStream"| bedrock[("Amazon Bedrock")]
    sm -->|"CreateEvent / ListEvents"| memory[("AgentCore Memory")]
```

Key points:

- `app.py` is the only HTTP-facing code. `agent.py` decides *what* the agent is made of, and
  `aws_read.py` is the only way the agent can reach AWS.
- A **new agent is built for every request**, so memory is tied to that request's session. The
  settings are loaded **once**, when the module is imported.

---

## 3. Request workflow (one chat message)

```mermaid
sequenceDiagram
    autonumber
    actor U as User / client<br/>(scripts/invoke.py)
    participant RT as AgentCore Runtime<br/>(IAM SigV4 auth)
    participant APP as app.invoke()
    participant AG as Strands Agent
    participant BR as Bedrock (Claude)
    participant T as aws_read tool
    participant AWS as AWS APIs
    participant MEM as AgentCore Memory

    U->>RT: InvokeAgentRuntime(runtimeSessionId ≥ 33 chars,<br/>qualifier=cloudops_agent_live, payload)
    RT->>APP: POST /invocations {prompt, actor_id}<br/>+ session-id header
    APP->>APP: validate prompt (string, not blank, ≤ MAX_PROMPT_CHARS)
    alt invalid payload
        APP-->>U: one SSE line: "Error: 'prompt' must be a non-empty string."
    end
    APP->>AG: build_agent(settings, session_id, actor_id)
    opt MEMORY_ID set and a session id present
        AG->>MEM: load earlier turns of this session
    end
    AG->>BR: prompt + system prompt + current time
    loop until the model stops calling tools
        BR-->>AG: tool call aws_read(service, operation, parameters)
        AG->>T: aws_read(...)
        T->>T: allow-list prefix? on deny-list?<br/>(refuses before any boto3 call)
        T->>AWS: boto3 client.operation(**parameters)
        AWS-->>T: JSON response
        T-->>AG: redacted, truncated JSON string
        AG->>BR: tool result
    end
    BR-->>AG: streamed text chunks
    AG-->>APP: events {"data": "..."}
    APP-->>U: SSE "data:" lines (text only)
    opt memory enabled
        AG->>MEM: CreateEvent (save this turn)
    end
    Note over APP: On any exception: log the details server-side,<br/>stream only "[error] The agent hit an internal error…"
```

---

## 4. How `aws_read` decides (read-only guard)

```mermaid
flowchart LR
    A["aws_read(service, operation)"] --> N["normalize<br/>DescribeInstances → describe_instances<br/>(then lower-case)"]
    N --> P{"starts with describe_ / list_ /<br/>get_ / lookup_ / search_?"}
    P -- no --> R1["Refused: not a read operation"]
    P -- yes --> D{"on DENIED_OPERATIONS, or name contains<br/>credentials / password / token / secret_value?"}
    D -- yes --> R2["Refused: returns secrets or credentials"]
    D -- no --> C{"real method on the boto3 client?"}
    C -- no --> R3["Refused: unknown operation/service"]
    C -- yes --> CALL["call boto3"]
    CALL -->|ClientError| E["'AWS error AccessDenied: …'<br/>(IAM is the second layer)"]
    CALL -->|ok| OUT["drop ResponseMetadata → redact secrets<br/>→ JSON → truncate to MAX_TOOL_OUTPUT_CHARS"]
```

The agent is read-only because of **two independent layers**:

1. The tool rules shown above.
2. The runtime IAM role. It has `ReadOnlyAccess` plus an explicit **Deny** on secret and data
   reads such as `s3:GetObject`, `ssm:GetParameter*`, `secretsmanager:GetSecretValue`, and
   `dynamodb:GetItem/Query/Scan`.

If you add new tools, do not weaken either layer.

---

## 5. AWS architecture

![AWS architecture with official AWS icons](diagrams/aws-architecture.png)

The image above is rendered from
[`diagrams/aws-architecture.drawio`](diagrams/aws-architecture.drawio); edit it in draw.io.
The same picture as a Mermaid diagram, which renders on GitHub without the image:

```mermaid
flowchart LR
    dev["Developer / CI"] -- "InvokeAgentRuntime<br/>SigV4" --> ep

    subgraph acct["AWS account · region ap-southeast-1"]
        subgraph ac["Amazon Bedrock AgentCore"]
            ep["Runtime endpoint<br/>cloudops_agent_live"] --> rt["Agent runtime<br/>cloudops_agent<br/>(arm64 container, PUBLIC network)"]
            mem["Memory<br/>cloudops_agent_memory<br/>(short-term events, 30 days)"]
        end
        ecr["Amazon ECR<br/>cloudops-agent<br/>(immutable tags, scan on push)"]
        role["IAM role<br/>cloudops-agent-runtime<br/>ReadOnlyAccess + explicit Deny"]
        br["Amazon Bedrock<br/>global.anthropic.claude-sonnet-5-5<br/>(inference profile)"]
        cw["CloudWatch Logs<br/>/aws/bedrock-agentcore/runtimes/…<br/>(30-day retention)"]
        xr["X-Ray / CloudWatch metrics<br/>(OpenTelemetry)"]
        svc["Your AWS resources<br/>(EC2, S3, Lambda, CloudWatch, …)<br/>read-only"]
    end

    ecr -- "image pull" --> rt
    rt -. "assumes" .-> role
    rt -- "InvokeModel" --> br
    rt -- "events" --> mem
    rt -- "logs" --> cw
    rt -- "traces/metrics" --> xr
    rt -- "aws_read (describe/list/get)" --> svc
```

All of these are created by Terraform in `infra/`. The exceptions are **ECR** and the
CI/state resources, which come from `infra/bootstrap/` (see §6).
---

## 6. Infrastructure layout (two Terraform configs)

```mermaid
flowchart TB
    subgraph boot["infra/bootstrap/ — applied ONCE by an admin, LOCAL state"]
        s3["S3 state bucket<br/>versioned · KMS · TLS-only · no public access"]
        oidc["IAM OIDC provider<br/>token.actions.githubusercontent.com"]
        dr["IAM role cloudops-agent-github-deploy<br/>trusts repo:&lt;owner/name&gt;:environment:production"]
        ecr2["ECR repo cloudops-agent"]
    end
    subgraph main["infra/ — applied by CI on every deploy, S3 backend<br/>key cloudops-agent/prod.tfstate (use_lockfile)"]
        rt2["aws_bedrockagentcore_agent_runtime"]
        ep2["aws_bedrockagentcore_agent_runtime_endpoint"]
        mem2["aws_bedrockagentcore_memory"]
        role2["aws_iam_role runtime + inline policy + read policies"]
        lg["aws_cloudwatch_log_group ×2"]
    end
    boot -- "outputs → GitHub repo variables<br/>(TF_STATE_BUCKET, AWS_DEPLOY_ROLE_ARN,<br/>ECR_REPOSITORY_URL/ARN)" --> main
```

Why are there two? Because of a chicken-and-egg problem. CI needs a role to assume and a bucket
for state, and the runtime needs an image in ECR, before `infra/` can be applied.

---

## 7. Delivery workflow (PR → production)

```mermaid
flowchart LR
    pr["Pull request"] --> ci
    subgraph ci["ci.yml (PRs + pushes to main)"]
        direction TB
        py["python: uv sync · ruff check · ruff format --check · pytest"]
        tf["terraform: fmt · validate (both configs) · trivy HIGH/CRITICAL"]
        sec["secrets: gitleaks over the full git history"]
        dk["docker: arm64 build (no push)"]
    end
    ci --> merge["merge to main"]
    merge --> dep
    subgraph dep["deploy.yml (push to main / manual)"]
        direction TB
        gate{{"environment: production<br/>required reviewer approves"}}
        gate --> auth["OIDC → assume deploy role<br/>(no static AWS keys)"]
        auth --> img["build + push arm64 image<br/>tag = git SHA (skipped if it already exists)"]
        img --> apply["terraform -chdir=infra apply<br/>-var image_tag=SHA"]
    end
    apply --> live["AgentCore creates a new runtime version<br/>endpoint cloudops_agent_live moves to it"]
```

---

## 8. Your first day: a checklist

1. **Install** [uv](https://docs.astral.sh/uv/), Docker (with buildx), Terraform ≥ 1.15, and AWS
   CLI v2.
2. **Clone and test.** No AWS access is needed for this step:

   ```bash
   uv sync
   uv run pytest            # 83 tests, ~1s, no AWS calls
   uv run ruff check . && uv run ruff format --check .
   ```
3. **Run it locally.** You need AWS credentials with Bedrock access in `ap-southeast-1`. Prefer
   a *read-only* profile, because locally the agent uses **your** credentials.

   ```bash
   uv run python -m cloudops_agent.app                     # terminal 1
   uv run python scripts/invoke.py --local                 # terminal 2 (interactive)
   ```
4. **Read the code in this order:** `config.py`, then `app.py`, then `agent.py`, then
   `tools/aws_read.py`. It is about 500 lines in total.
5. **Try a change.** Add a test in `tests/`, watch it fail, make it pass, and open a PR. CI
   runs everything listed in §7.
6. **Talk to the deployed agent**, once you have IAM access to it:

   ```bash
   export AGENT_RUNTIME_ARN=<terraform output agent_runtime_arn>
   uv run python scripts/invoke.py
   ```

## 9. Adding a new tool (the hackathon path)

1. Create `src/cloudops_agent/tools/<name>.py` with a factory `make_<name>_tool(settings) -> AgentTool`.
   Inside it, define a function decorated with `@tool` from `strands`, and give it a clear
   docstring, because the model reads it. Return strings.
2. Register the tool in `build_agent()` in `src/cloudops_agent/agent.py`, in the
   `tools=[...]` list.
3. Inject external clients through the factory, the way `session_factory` works in
   `aws_read`. That lets tests pass in fakes and never call the network.
4. Update `tests/test_agent.py::test_agent_has_only_aws_read_tool`, which pins the tool list.
5. If the tool needs secrets, such as an API token, decide with the team how to provide them.
   There is **no secrets mechanism yet** (see [CONCERNS.md](codebase/CONCERNS.md)).
6. If it needs new AWS permissions, add them to the runtime role in `infra/iam.tf`, as narrow
   as possible.

## 10. Glossary

| Term | Meaning |
|---|---|
| **Strands Agents** | AWS's open-source Python SDK for building agents. It runs the loop of model → tool → model. |
| **AgentCore Runtime** | Serverless host for agent containers. It is invoked with `InvokeAgentRuntime` and gives each session its own microVM. |
| **Runtime endpoint** (`cloudops_agent_live`) | A named pointer to a runtime version. Callers pass it as `qualifier`. |
| **AgentCore Memory** | A managed store of conversation events, keyed by `actor_id` and `session_id`. |
| **Inference profile** (`global.…`) | A Bedrock ID that routes model calls across regions for capacity. |
| **Session id** | The `runtimeSessionId`. It must be **at least 33 characters**. The client generates `cli-<uuid hex>`. |
| **OIDC deploy role** | The IAM role GitHub Actions assumes with a short-lived token. There are no stored AWS keys. |
| **`legacy/`** | The previous implementation (ping monitor, approval Lambdas, RAG, Cognito, Gateway). It is not maintained. |
