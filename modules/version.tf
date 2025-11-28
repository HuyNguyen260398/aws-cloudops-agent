terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Cấu hình Backend S3 cho Terraform State
  backend "s3" {
    bucket         = "test-rag-agent-bucket"
    key            = "rag-agent/terraform.tfstate"
    region         = "ap-southeast-1"        
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
}

provider "aws" {
  alias  = "bedrock"
  region = var.bedrock_region
}

