# Short-term conversation memory only (no long-term strategies). AWS-managed encryption.
resource "aws_bedrockagentcore_memory" "agent" {
  name                  = "cloudops_agent_memory"
  description           = "Conversation memory for the CloudOps agent"
  event_expiry_duration = var.memory_event_expiry_days
}
