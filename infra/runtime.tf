resource "aws_bedrockagentcore_agent_runtime" "agent" {
  agent_runtime_name = local.runtime_name
  description        = "Read-only AWS CloudOps agent"
  role_arn           = aws_iam_role.runtime.arn

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${var.ecr_repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  # No authorizer_configuration: inbound auth is IAM (SigV4), the default.
  # AWS_REGION is provided by the runtime.
  environment_variables = {
    MODEL_ID  = var.model_id
    MEMORY_ID = aws_bedrockagentcore_memory.agent.id
    LOG_LEVEL = var.log_level
  }

  # The role's policies must exist before the runtime starts pulling and invoking.
  depends_on = [
    aws_iam_role_policy.runtime,
    aws_iam_role_policy_attachment.read,
  ]
}

resource "aws_bedrockagentcore_agent_runtime_endpoint" "live" {
  name             = local.endpoint_name
  agent_runtime_id = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id
  # Follow each new runtime version, so a deploy moves the endpoint to the new image.
  agent_runtime_version = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_version
}

# AgentCore writes runtime logs to /aws/bedrock-agentcore/runtimes/<runtime-id>-<endpoint>.
# Creating the groups here sets retention (the runtime would otherwise create them with none).
resource "aws_cloudwatch_log_group" "runtime" {
  for_each = toset([local.endpoint_name, "DEFAULT"])

  name              = "/aws/bedrock-agentcore/runtimes/${aws_bedrockagentcore_agent_runtime.agent.agent_runtime_id}-${each.key}"
  retention_in_days = var.log_retention_days
}
