output "state_bucket_name" {
  description = "Set as GitHub variable TF_STATE_BUCKET."
  value       = aws_s3_bucket.state.bucket
}

output "deploy_role_arn" {
  description = "Set as GitHub variable AWS_DEPLOY_ROLE_ARN."
  value       = aws_iam_role.deploy.arn
}

output "ecr_repository_url" {
  description = "Set as GitHub variable ECR_REPOSITORY_URL."
  value       = aws_ecr_repository.agent.repository_url
}

output "ecr_repository_arn" {
  description = "Set as GitHub variable ECR_REPOSITORY_ARN."
  value       = aws_ecr_repository.agent.arn
}
