variable "region" {
  description = "AWS region for the agent."
  type        = string
  default     = "ap-southeast-1"
}

variable "environment" {
  description = "Environment name (used in tags and the state key)."
  type        = string
  default     = "prod"
}

variable "ecr_repository_url" {
  description = "ECR repository URL (bootstrap output ecr_repository_url)."
  type        = string
}

variable "ecr_repository_arn" {
  description = "ECR repository ARN (bootstrap output ecr_repository_arn)."
  type        = string
}

variable "image_tag" {
  description = "Image tag to deploy (CI uses the git commit SHA)."
  type        = string
}

variable "model_id" {
  description = "Bedrock inference profile ID. Keep in sync with DEFAULT_MODEL_ID in src/cloudops_agent/config.py."
  type        = string
  default     = "global.anthropic.claude-sonnet-5-5"
}

variable "agent_read_policy_arns" {
  description = "Managed policies attached to the runtime role for the aws_read tool. Keep them read-only."
  type        = list(string)
  default     = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
}

variable "memory_event_expiry_days" {
  description = "Days AgentCore Memory keeps short-term conversation events."
  type        = number
  default     = 30
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the runtime."
  type        = number
  default     = 30
}

variable "log_level" {
  description = "Agent LOG_LEVEL."
  type        = string
  default     = "INFO"
}
