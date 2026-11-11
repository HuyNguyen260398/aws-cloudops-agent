output "documents_bucket_name" {
  description = "Tên Bucket lưu trữ tài liệu RAG."
  value       = aws_s3_bucket.rag_documents.id
}

output "knowledge_base_id" {
  description = "ID của Bedrock Knowledge Base đã tạo."
  value       = aws_bedrockagent_knowledge_base.kb.id
}