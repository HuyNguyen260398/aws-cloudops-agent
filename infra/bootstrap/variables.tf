variable "region" {
  description = "AWS region for the state bucket, ECR repository and agent."
  type        = string
  default     = "ap-southeast-1"
}

variable "github_repository" {
  description = "GitHub repository allowed to deploy, as \"owner/name\"."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must look like \"owner/name\"."
  }
}

variable "state_bucket_name" {
  description = "Globally unique name for the Terraform state bucket."
  type        = string
}

variable "ecr_repository_name" {
  description = "ECR repository for the agent image."
  type        = string
  default     = "cloudops-agent"
}

variable "runtime_read_policy_arns" {
  description = "Managed policies the deploy role may attach to the runtime role. Must include every ARN in infra's agent_read_policy_arns."
  type        = list(string)
  default     = ["arn:aws:iam::aws:policy/ReadOnlyAccess"]
}
