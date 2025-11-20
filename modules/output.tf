output "api_endpoint" {
  description = "API Gateway Endpoint cho Agent."
  value       = aws_apigatewayv2_stage.default_stage.invoke_url
}

output "documents_bucket_name" {
  description = "Tên Bucket lưu trữ tài liệu RAG."
  value       = aws_s3_bucket.rag_documents.id
}

output "artifacts_bucket_name" {
  description = "Tên Bucket lưu trữ artifacts Lambda ZIP."
  value       = data.aws_s3_bucket.rag_artifacts.id
}

output "knowledge_base_id" {
  description = "ID của Bedrock Knowledge Base đã tạo."
  value       = aws_bedrockagent_knowledge_base.kb.id
}