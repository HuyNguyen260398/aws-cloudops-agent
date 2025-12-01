# Bucket Documents (RAG data source) - in Bedrock region (ap-southeast-2)
resource "aws_s3_bucket" "rag_documents" {
  provider = aws.bedrock
  bucket = "${var.project}-documents-${var.bedrock_region}-${data.aws_caller_identity.current.account_id}"
  tags = { Name = "${var.project}-documents-${var.bedrock_region}" }
}

# Get ID Account to create bucket name
data "aws_caller_identity" "current" {}

# Securicy of Bucket Documents
resource "aws_s3_bucket_public_access_block" "rag_documents_block" {
  provider = aws.bedrock
  bucket = aws_s3_bucket.rag_documents.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
