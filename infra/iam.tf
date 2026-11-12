locals {
  inference_profile_arn = "arn:${local.partition}:bedrock:${var.region}:${local.account_id}:inference-profile/${var.model_id}"
  runtime_log_group_arn = "arn:${local.partition}:logs:${var.region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*"
}

data "aws_iam_policy_document" "runtime_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:${local.partition}:bedrock-agentcore:${var.region}:${local.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "runtime" {
  name               = "cloudops-agent-runtime"
  description        = "Execution role for the CloudOps agent on AgentCore Runtime"
  assume_role_policy = data.aws_iam_policy_document.runtime_trust.json
}

data "aws_iam_policy_document" "runtime" {
  # 0. Explicit deny for reads that return secrets, credentials, or customer data, whatever
  #    the attached read policies allow (ReadOnlyAccess grants several of them).
  statement {
    sid    = "DenySecretAndDataReads"
    effect = "Deny"
    actions = [
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:GetDataAccess",
      "ssm:GetParameter",
      "ssm:GetParameters",
      "ssm:GetParametersByPath",
      "ssm:GetParameterHistory",
      "secretsmanager:GetSecretValue",
      "secretsmanager:BatchGetSecretValue",
      "lambda:GetFunction",
      "dynamodb:GetItem",
      "dynamodb:BatchGetItem",
      "dynamodb:Query",
      "dynamodb:Scan",
      "kinesis:GetRecords",
      "ec2:GetPasswordData",
      "redshift:GetClusterCredentials",
      "redshift:GetClusterCredentialsWithIAM",
      "redshift-serverless:GetCredentials",
      "glue:GetConnection",
      "glue:GetConnections",
      "lightsail:GetInstanceAccessDetails",
      "lightsail:GetRelationalDatabaseMasterUserPassword",
    ]
    resources = ["*"]
  }

  # 1. Invoke the chosen inference profile, and its underlying models only through that profile.
  statement {
    sid       = "InvokeInferenceProfile"
    actions   = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [local.inference_profile_arn]
  }

  statement {
    sid     = "InvokeModelsViaProfile"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    # Global profiles route to region-less foundation-model ARNs; list both forms.
    resources = [
      "arn:${local.partition}:bedrock:*::foundation-model/*",
      "arn:${local.partition}:bedrock:::foundation-model/*",
    ]

    condition {
      test     = "StringEquals"
      variable = "bedrock:InferenceProfileArn"
      values   = [local.inference_profile_arn]
    }
  }

  # 2. Conversation memory: this memory only.
  statement {
    sid = "Memory"
    actions = [
      "bedrock-agentcore:CreateEvent",
      "bedrock-agentcore:DeleteEvent",
      "bedrock-agentcore:GetEvent",
      "bedrock-agentcore:GetMemoryRecord",
      "bedrock-agentcore:ListEvents",
      "bedrock-agentcore:ListMemoryRecords",
      "bedrock-agentcore:ListSessions",
      "bedrock-agentcore:RetrieveMemoryRecords",
    ]
    resources = [aws_bedrockagentcore_memory.agent.arn]
  }

  # 3. Pull the agent image.
  statement {
    sid       = "EcrPull"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [var.ecr_repository_arn]
  }

  # Required by AWS: GetAuthorizationToken does not support resource-level permissions.
  statement {
    sid       = "EcrAuth"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  # 4. Runtime logs.
  statement {
    sid = "Logs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:DescribeLogStreams",
      "logs:PutLogEvents",
    ]
    resources = [local.runtime_log_group_arn, "${local.runtime_log_group_arn}:*"]
  }

  # 5. Tracing. Required by AWS: X-Ray has no resource-level permissions.
  statement {
    sid = "XRay"
    actions = [
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
      "xray:PutTelemetryRecords",
      "xray:PutTraceSegments",
    ]
    resources = ["*"]
  }

  # 6. Metrics, limited to the AgentCore namespace (PutMetricData has no resource ARN).
  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }
}

resource "aws_iam_role_policy" "runtime" {
  name   = "cloudops-agent-runtime"
  role   = aws_iam_role.runtime.id
  policy = data.aws_iam_policy_document.runtime.json
}

# Read-only access for the aws_read tool. Mutations fail here even if the tool's own
# allow-list were bypassed.
resource "aws_iam_role_policy_attachment" "read" {
  for_each = toset(var.agent_read_policy_arns)

  role       = aws_iam_role.runtime.name
  policy_arn = each.value
}
