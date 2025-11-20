# IAM Role cho Bedrock Knowledge Base (Assume Role: bedrock.amazonaws.com)
resource "aws_iam_role" "kb_service_role" {
  name = "${var.project}-kb-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      },
    ]
  })
}

# Policy cho phép KB truy cập S3 và OpenSearch
resource "aws_iam_role_policy" "kb_policy" {
  name = "${var.project}-kb-policy"
  role = aws_iam_role.kb_service_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Quyền S3 (Documents Bucket)
      {
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.rag_documents.arn, "${aws_s3_bucket.rag_documents.arn}/*"]
      },
      # Quyền OpenSearch Serverless
      {
        Effect = "Allow"
        Action = ["aoss:APIAccessAll"] 
        Resource = aws_opensearchserverless_collection.rag_collection.arn
      }
    ]
  })
}

# Bedrock Knowledge Base
resource "aws_bedrockagent_knowledge_base" "kb" {
  name        = "${var.project}-kb"
  description = "Knowledge Base for RAG"
  role_arn    = aws_iam_role.kb_service_role.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.region}::foundation-model/amazon.titan-embed-text-v2:0"
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.rag_collection.arn
      vector_index_name = "rag-agent-index"
      field_mapping {
        vector_field   = "vector"
        text_field     = "text"
        metadata_field = "metadata"
      }
    }
  }

  depends_on = [
    null_resource.create_index
  ]
}

# Data Source (Kết nối S3 Documents với KB)
resource "aws_bedrockagent_data_source" "docs_data_source" {
  name               = "docs-data-source"
  knowledge_base_id  = aws_bedrockagent_knowledge_base.kb.id
  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.rag_documents.arn
      inclusion_prefixes = ["docs/"] 
    }
  }
}