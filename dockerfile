FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-cache

COPY config/static-config.yaml ./config/
COPY config/dynamic-config.yaml ./config/

COPY src/utils/config_manager.py ./utils/
COPY src/utils/config_validator.py ./utils/
COPY src/utils/config.py ./utils/
COPY src/utils/mylogger.py ./utils/
COPY src/utils/responses.py ./utils/
COPY src/utils/query_extractor.py ./utils/

COPY src/agents/aws_cloudops_agent.py ./agents/
COPY src/components/auth.py ./components/
COPY src/components/gateway.py ./components/
COPY src/components/mcp.py ./components/
COPY src/components/memory.py ./components/
COPY src/components/conversation_manager.py ./components/

COPY src/tools/kb_retrieval.py ./tools/

COPY src/agent_runtime.py ./

# Signal that this is running in Docker for host binding logic
#ENV DOCKER_CONTAINER=1

# RUN uv add aws_opentelemetry_distro_genai_beta>=0.1.2

# Create non-root user
# RUN useradd -m -u 1000 bedrock_agentcore
# USER bedrock_agentcore

# Expose port 8080 (AgentCore requirement)
EXPOSE 8080

# Comment below to run in agentcore runtime
# Uncomment below to run in local container on desktop
CMD ["uv", "run", "uvicorn", "agent_runtime:app", "--host", "0.0.0.0", "--port", "8080"]

# Uncomment below to run in agentcore runtime
# Comment below to run in local container on desktop
# CMD ["opentelemetry-instrument", "python", "agent_runtime.py"]
