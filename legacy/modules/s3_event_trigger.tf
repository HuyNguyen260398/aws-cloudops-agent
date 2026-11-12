# S3 Event Notification to trigger Lambda Ingestion automatically
# when new files are uploaded to docs/ prefix

# IMPORTANT: Both Lambda and S3 must be in SAME region (ap-southeast-2)
# Lambda permission must be in same region as Lambda function
resource "aws_lambda_permission" "allow_s3_invoke" {
  provider = aws.bedrock  # Same as Lambda Ingest (ap-southeast-2)

  statement_id   = "AllowS3Invoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.ingest.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.rag_documents.arn
  source_account = data.aws_caller_identity.current.account_id
}

# S3 Bucket Notification - must be in same region as S3 bucket (ap-southeast-2)
resource "aws_s3_bucket_notification" "document_upload_trigger" {
  provider = aws.bedrock  # S3 bucket is in ap-southeast-2
  bucket   = aws_s3_bucket.rag_documents.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingest.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "docs/"  # Only trigger for files in docs/ folder
    filter_suffix       = ""       # All file types
  }

  depends_on = [aws_lambda_permission.allow_s3_invoke]
}
