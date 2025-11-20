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

variable "artifact_bucket_name" {
  description = "Tên S3 Bucket để lưu trữ các Artifact (zip files)."
  type        = string
}

variable "ingest_artifact_key" {
  description = "Key S3 của file zip Lambda Ingest mới nhất."
  type        = string
}

variable "retrieve_artifact_key" {
  description = "Key S3 của file zip Lambda Retrieve mới nhất."
  type        = string
}