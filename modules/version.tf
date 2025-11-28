terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
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

  skip_metadata_api_check     = true
  skip_region_validation      = true
  skip_credentials_validation = true
  skip_requesting_account_id  = true

  # Disable SSL verification for proxy
  insecure = true
}

provider "aws" {
  alias  = "bedrock"
  region = var.bedrock_region

  # Disable SSL verification for proxy
  insecure = true
}

