"""`aws_read`: a read-only boto3 tool for the agent.

Two layers keep the agent read-only. The runtime IAM role grants only read access, and this
tool refuses every operation that is not a read before boto3 is called. Some reads return
secrets or credentials; those are denied explicitly.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import boto3
from botocore import xform_name
from botocore.exceptions import BotoCoreError, ClientError, UnknownServiceError
from strands import tool
from strands.types.tools import AgentTool

from cloudops_agent.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_PREFIXES = ("describe_", "list_", "get_", "lookup_", "search_")

# Reads whose responses contain secrets, credentials, or presigned URLs.
DENIED_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("secretsmanager", "get_secret_value"),
        ("secretsmanager", "batch_get_secret_value"),
        ("ssm", "get_parameter"),
        ("ssm", "get_parameters"),
        ("ssm", "get_parameters_by_path"),
        ("ssm", "get_parameter_history"),
        ("s3", "get_object"),
        ("ecr", "get_authorization_token"),
        ("ecr-public", "get_authorization_token"),
        ("codeartifact", "get_authorization_token"),
        ("ec2", "get_password_data"),
        ("redshift", "get_cluster_credentials"),
        ("redshift", "get_cluster_credentials_with_iam"),
        ("cognito-identity", "get_credentials_for_identity"),
        ("cognito-identity", "get_open_id_token"),
        ("cognito-identity", "get_open_id_token_for_developer_identity"),
        ("sts", "get_session_token"),
        ("sts", "get_federation_token"),
        ("sso", "get_role_credentials"),
        ("lightsail", "get_instance_access_details"),
        ("lightsail", "get_relational_database_master_user_password"),
        ("lambda", "get_function"),  # response contains a presigned code URL
    }
)

TRUNCATION_NOTE = "\n...[truncated: {shown} of {total} chars shown]"


def _normalize(service: str, operation: str) -> tuple[str, str]:
    return service.strip().lower(), xform_name(operation.strip()).lower()


def is_allowed_operation(service: str, operation: str) -> tuple[bool, str]:
    """Return (allowed, reason) for a boto3 service/operation, before any client exists."""
    svc, op = _normalize(service, operation)
    if not op.startswith(ALLOWED_PREFIXES):
        return False, (
            f"'{op}' is not a read operation. aws_read only allows operations starting with "
            f"{', '.join(ALLOWED_PREFIXES)}. This agent is read-only."
        )
    if (svc, op) in DENIED_OPERATIONS:
        return False, f"'{svc}.{op}' can return secrets or credentials and is blocked."
    return True, "ok"


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + TRUNCATION_NOTE.format(shown=limit, total=len(text))


def make_aws_read_tool(
    settings: Settings,
    session_factory: Callable[[], boto3.Session] = boto3.Session,
) -> AgentTool:
    """Build the `aws_read` tool bound to `settings`."""

    @tool(name="aws_read")
    def aws_read(
        service: str,
        operation: str,
        parameters: dict[str, Any] | None = None,
        region: str | None = None,
    ) -> str:
        """Call a read-only AWS API operation with boto3 and return its JSON response.

        Only describe_*, list_*, get_*, lookup_* and search_* operations are allowed, and
        operations that return secrets or credentials are blocked. Large responses are
        truncated; narrow them with filters or pagination parameters.

        Args:
            service: boto3 service name, e.g. "ec2", "s3", "cloudwatch", "logs".
            operation: Operation name in snake_case or CamelCase, e.g. "describe_instances".
            parameters: Keyword arguments for the operation, e.g. {"MaxResults": 50}.
            region: AWS region; defaults to the agent's region.
        """
        allowed, reason = is_allowed_operation(service, operation)
        if not allowed:
            return f"Refused: {reason}"
        if parameters is not None and not isinstance(parameters, dict):
            return "Refused: 'parameters' must be an object of keyword arguments."
        svc, op = _normalize(service, operation)
        try:
            client = session_factory().client(svc, region_name=region or settings.region)
        except UnknownServiceError:
            return f"Refused: unknown AWS service '{svc}'."
        if op not in client.meta.method_to_api_mapping:
            return f"Refused: '{op}' is not an operation of the '{svc}' client."
        try:
            response = getattr(client, op)(**(parameters or {}))
        except ClientError as exc:
            err = exc.response.get("Error", {})
            return f"AWS error {err.get('Code', 'Unknown')}: {err.get('Message', '')}"
        except BotoCoreError as exc:
            logger.warning("aws_read %s.%s failed: %s", svc, op, exc)
            return f"AWS error: {exc}"
        response = dict(response or {})
        response.pop("ResponseMetadata", None)
        text = json.dumps(response, default=str)
        return _truncate(text, settings.max_tool_output_chars)

    return aws_read
