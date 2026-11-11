output "agent_runtime_arn" {
  description = "Use with scripts/invoke.py --runtime-arn (or AGENT_RUNTIME_ARN)."
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}

output "agent_runtime_endpoint_name" {
  description = "Endpoint qualifier for InvokeAgentRuntime."
  value       = aws_bedrockagentcore_agent_runtime_endpoint.live.name
}

output "memory_id" {
  description = "AgentCore Memory ID (set as MEMORY_ID to use it locally)."
  value       = aws_bedrockagentcore_memory.agent.id
}

output "runtime_role_arn" {
  description = "Runtime execution role."
  value       = aws_iam_role.runtime.arn
}
