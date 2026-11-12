# syntax=docker/dockerfile:1
# AgentCore Runtime requires linux/arm64.

# ---- builder: resolve and install dependencies into /app/.venv ----
# ghcr.io/astral-sh/uv:python3.13-bookworm-slim
FROM --platform=linux/arm64 ghcr.io/astral-sh/uv@sha256:531f855bda2c73cd6ef67d56b733b357cea384185b3022bd09f05e002cd144ca AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app

# Dependencies first (cached unless pyproject.toml/uv.lock change)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-dev --no-editable --no-install-project

# Then the project itself
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---- final: slim runtime, no build tools, non-root ----
# python:3.13-slim-bookworm
FROM --platform=linux/arm64 python@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder --chown=root:root /app/.venv /app/.venv

# DOCKER_CONTAINER makes BedrockAgentCoreApp bind 0.0.0.0 instead of 127.0.0.1.
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DOCKER_CONTAINER=1
WORKDIR /app
USER app

EXPOSE 8080
CMD ["opentelemetry-instrument", "python", "-m", "cloudops_agent.app"]
