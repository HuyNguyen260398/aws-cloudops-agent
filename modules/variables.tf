variable "project" {
  description = "Tên dự án được sử dụng làm tiền tố cho các tài nguyên."
  type        = string
  default     = "rag-agent-system"
}

variable "region" {
  description = "AWS region để triển khai."
  type        = string
  default     = "ap-southeast-1"
}

variable "bedrock_region" {
  description = "AWS region cho Bedrock Knowledge Base (có Titan Embed v2)."
  type        = string
  default     = "ap-southeast-2"
}

