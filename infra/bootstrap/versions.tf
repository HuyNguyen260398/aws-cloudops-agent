# Applied once by an admin with LOCAL state (terraform.tfstate in this directory).
# Keep that state file safe (it is git-ignored); see README "First-time AWS setup".
terraform {
  required_version = ">= 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = "cloudops-agent"
      ManagedBy = "terraform"
      Stack     = "bootstrap"
    }
  }
}
