"""Local tools for the CloudOps agent. Future tool sets (spacelift/, slack/) go here."""

from cloudops_agent.tools.aws_read import is_allowed_operation, make_aws_read_tool

__all__ = ["is_allowed_operation", "make_aws_read_tool"]
