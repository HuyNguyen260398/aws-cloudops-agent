terraform {
  required_version = ">= 1.15"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.72"
    }
  }

  # Partial configuration: pass -backend-config=backend.hcl (see backend.hcl.example).
  backend "s3" {}
}
