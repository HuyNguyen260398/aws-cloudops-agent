# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_exec" {
  name = "${var.project}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
}

# IAM Policy for Lambda Functions
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project}-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch Logs
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },

      # S3 Bucket Access
      {
        Sid    = "S3Access"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket",
          "s3:PutObject",
        ]
        Resource = [
          "${data.aws_s3_bucket.rag_artifacts.arn}/*",
          "${aws_s3_bucket.rag_documents.arn}/*",
          data.aws_s3_bucket.rag_artifacts.arn,
          aws_s3_bucket.rag_documents.arn,
        ]
      },

      # Bedrock Model Invocation and Retrieval
      {
        Sid    = "BedrockInvokeAndRetrieve"
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock:Retrieve",
          "bedrock:RetrieveAndGenerate"
        ]
        Resource = "*"
      },

      # Bedrock Knowledge Base Operations
      {
        Sid    = "BedrockKnowledgeBase"
        Effect = "Allow"
        Action = [
          "bedrock:ListDataSources",
          "bedrock:GetDataSource",
          "bedrock:StartIngestionJob",
          "bedrock:GetIngestionJob",
          "bedrock:ListIngestionJobs",
          "bedrock:GetKnowledgeBase"
        ]
        Resource = "*"
      },

      # Bedrock Agent Runtime (for KB retrieval via agent runtime)
      {
        Sid    = "BedrockAgentRuntime"
        Effect = "Allow"
        Action = [
          "bedrock-agent-runtime:Retrieve",
          "bedrock-agent-runtime:RetrieveAndGenerate"
        ]
        Resource = "*"
      },

      # Bedrock Agent Operations (for ingestion)
      {
        Sid    = "BedrockAgentOperations"
        Effect = "Allow"
        Action = [
          "bedrock-agent:StartIngestionJob",
          "bedrock-agent:GetIngestionJob",
          "bedrock-agent:ListIngestionJobs",
          "bedrock-agent:ListDataSources",
          "bedrock-agent:GetDataSource"
        ]
        Resource = "*"
      },

      # OpenSearch Serverless Access
      {
        Sid      = "OpenSearchServerless"
        Effect   = "Allow"
        Action   = ["aoss:APIAccessAll"]
        Resource = aws_opensearchserverless_collection.rag_collection.arn
      }
    ]
  })
}
