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


resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project}-lambda-policy"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # CloudWatch
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      # Bucket
      {
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

      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel",
          "bedrock-agent:StartIngestionJob",
          "bedrock-agent:ListDataSources",
        ]
        Resource = "*"
      },

      {
        Effect = "Allow"
        Action = [
          "aoss:APIAccessAll"
        ]
        Resource = aws_opensearchserverless_collection.rag_collection.arn
      }
    ]
  })
}