terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Cấu hình Backend S3 cho Terraform State
  backend "s3" {
    bucket         = "test-rag-agent-bucket" # THAY THẾ bằng tên Bucket S3 duy nhất của bạn
    key            = "rag-agent/terraform.tfstate"
    region         = "ap-southeast-1"           # THAY THẾ bằng region chính
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
}

