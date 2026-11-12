# Lambda Ingestion - triggers KB ingestion when files uploaded to S3
# MUST be in same region as S3 Documents bucket (ap-southeast-2) for S3 event trigger
# Uses local code (builds on terraform apply)

data "archive_file" "lambda_ingest_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../assets/ingest_lambda"
  output_path = "${path.module}/../build/lambda_ingest.zip"
}

resource "aws_lambda_function" "ingest" {
  provider = aws.bedrock # Deploy to ap-southeast-2 (same as S3 Documents and Knowledge Base)

  function_name = "${var.project}-ingest"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.12"

  filename         = data.archive_file.lambda_ingest_zip.output_path
  source_code_hash = data.archive_file.lambda_ingest_zip.output_base64sha256

  timeout     = 30
  memory_size = 512

  environment {
    variables = {
      KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.kb.id
      BEDROCK_REGION    = var.bedrock_region
    }
  }
}
