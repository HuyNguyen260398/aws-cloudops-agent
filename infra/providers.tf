provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = "cloudops-agent"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  partition  = data.aws_partition.current.partition

  runtime_name  = "cloudops_agent"
  endpoint_name = "cloudops_agent_live"
}
