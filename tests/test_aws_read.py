import json

import pytest
from botocore.exceptions import ClientError

from cloudops_agent.config import load_settings
from cloudops_agent.tools.aws_read import is_allowed_operation, make_aws_read_tool


@pytest.mark.parametrize(
    "svc,op",
    [
        ("ec2", "DescribeInstances"),
        ("s3", "list_buckets"),
        ("cloudwatch", "GetMetricData"),
        ("logs", "describe_log_groups"),
    ],
)
def test_read_ops_allowed(svc, op):
    assert is_allowed_operation(svc, op)[0] is True


@pytest.mark.parametrize(
    "svc,op",
    [
        ("s3", "DeleteBucket"),
        ("ec2", "terminate_instances"),
        ("ec2", "RunInstances"),
        ("iam", "CreateUser"),
        ("lambda", "invoke"),
        ("secretsmanager", "GetSecretValue"),
        ("secretsmanager", "batch_get_secret_value"),
        ("s3", "get_object"),
        ("ssm", "get_parameter"),
        ("ssm", "GetParametersByPath"),
        ("ecr", "GetAuthorizationToken"),
        ("ec2", "get_password_data"),
        ("sts", "get_session_token"),
        ("lambda", "GetFunction"),
    ],
)
def test_mutating_or_sensitive_refused(svc, op):
    assert is_allowed_operation(svc, op)[0] is False


class FakeClient:
    def __init__(self, response=None, error=None):
        self.calls = []
        self._response = response
        self._error = error
        self.meta = type(
            "Meta",
            (),
            {"method_to_api_mapping": {"list_buckets": "ListBuckets", "delete_bucket": "x"}},
        )()

    def list_buckets(self, **kwargs):
        self.calls.append(("list_buckets", kwargs))
        if self._error:
            raise self._error
        return self._response

    def delete_bucket(self, **kwargs):
        self.calls.append(("delete_bucket", kwargs))
        return {}


class FakeSession:
    def __init__(self, client):
        self._client = client
        self.client_args = []

    def client(self, service, region_name=None):
        self.client_args.append((service, region_name))
        return self._client


def make_tool(client, **env):
    settings = load_settings({k.upper(): str(v) for k, v in env.items()})
    session = FakeSession(client)
    return make_aws_read_tool(settings, session_factory=lambda: session), session


def test_tool_is_named_aws_read():
    tool, _ = make_tool(FakeClient())
    assert tool.tool_name == "aws_read"


def test_refused_op_never_calls_boto3():
    client = FakeClient()
    tool, session = make_tool(client)
    out = tool(service="s3", operation="DeleteBucket", parameters={"Bucket": "b"})
    assert out.startswith("Refused:")
    assert client.calls == []
    assert session.client_args == []


def test_unknown_operation_refused():
    client = FakeClient()
    tool, _ = make_tool(client)
    out = tool(service="s3", operation="describe_nonexistent")
    assert out.startswith("Refused:")
    assert client.calls == []


def test_response_metadata_stripped_and_json():
    tool, _ = make_tool(FakeClient(response={"Buckets": [], "ResponseMetadata": {}}))
    out = tool(service="s3", operation="ListBuckets")
    assert json.loads(out) == {"Buckets": []}


def test_parameters_and_region_passed_through():
    client = FakeClient(response={"Buckets": []})
    tool, session = make_tool(client)
    tool(service="s3", operation="list_buckets", parameters={"MaxBuckets": 5}, region="us-east-1")
    assert client.calls == [("list_buckets", {"MaxBuckets": 5})]
    assert session.client_args == [("s3", "us-east-1")]


def test_default_region_from_settings():
    tool, session = make_tool(FakeClient(response={}), aws_region="eu-west-1")
    tool(service="s3", operation="list_buckets")
    assert session.client_args == [("s3", "eu-west-1")]


def test_large_output_truncated():
    buckets = [{"Name": f"bucket-{i}"} for i in range(5000)]
    tool, _ = make_tool(FakeClient(response={"Buckets": buckets}), max_tool_output_chars=1000)
    out = tool(service="s3", operation="list_buckets")
    assert isinstance(out, str)
    assert len(out) <= 1000 + 80
    assert "...[truncated:" in out


def test_client_error_reported():
    err = ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "ListBuckets")
    tool, _ = make_tool(FakeClient(error=err))
    out = tool(service="s3", operation="list_buckets")
    assert out == "AWS error AccessDenied: no"


@pytest.mark.parametrize("op", ["get_Secret_Value", "Get_Secret_Value", "GET_SECRET_VALUE"])
def test_denylist_is_case_insensitive(op):
    allowed, reason = is_allowed_operation("SecretsManager", op)
    assert allowed is False
    assert "secrets or credentials" in reason
