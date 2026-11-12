"""Static guards on IAM policy shape in the Terraform (no AWS calls)."""

import re
from pathlib import Path

INFRA = Path(__file__).resolve().parents[1] / "infra"


def _statement(tf: str, sid: str) -> str:
    match = re.search(rf'sid\s*=\s*"{sid}"(.*?)\n  }}\n', tf, re.S)
    assert match, f"statement {sid} not found"
    return match.group(1)


def test_deploy_role_cannot_modify_its_own_role():
    tf = (INFRA / "bootstrap" / "main.tf").read_text()
    deploy_role_name = re.search(r'resource "aws_iam_role" "deploy" {\s*name\s*=\s*"([^"]+)"', tf)
    assert deploy_role_name
    # No wildcard role resources that could match the deploy role itself.
    assert ":role/cloudops-agent-*" not in tf
    iam_resources = re.findall(r'":role/([^"]+)"|role/([A-Za-z0-9_+=,.@*-]+)"', tf)
    names = {a or b for a, b in iam_resources}
    assert deploy_role_name.group(1) not in names


def test_deploy_role_passrole_limited_to_agentcore():
    tf = (INFRA / "bootstrap" / "main.tf").read_text()
    stmt = _statement(tf, "PassRuntimeRole")
    assert '"iam:PassRole"' in stmt
    assert "iam:PassedToService" in stmt
    assert "bedrock-agentcore.amazonaws.com" in stmt


def test_deploy_role_attach_limited_to_allowed_policies():
    tf = (INFRA / "bootstrap" / "main.tf").read_text()
    stmt = _statement(tf, "RuntimeRolePolicyAttachments")
    assert '"iam:AttachRolePolicy"' in stmt
    assert "iam:PolicyARN" in stmt
    assert "var.runtime_read_policy_arns" in stmt


def test_runtime_role_explicitly_denies_secret_reads():
    tf = (INFRA / "iam.tf").read_text()
    stmt = _statement(tf, "DenySecretAndDataReads")
    assert 'effect = "Deny"' in stmt.replace("  ", " ") or 'effect  = "Deny"' in stmt
    for action in [
        "s3:GetObject",
        "ssm:GetParameter",
        "secretsmanager:GetSecretValue",
        "lambda:GetFunction",
        "dynamodb:GetItem",
        "kinesis:GetRecords",
        "ec2:GetPasswordData",
    ]:
        assert f'"{action}' in stmt, action
