# Lambda Retriever (Sử dụng Artifact ZIP từ GitHub Actions)
resource "aws_lambda_function" "retrieve" {
  function_name = "${var.project}-retrieve"
  role          = aws_iam_role.lambda_exec.arn
  handler       = "lambda_handler.lambda_handler"
  runtime       = "python3.12"

  s3_bucket = data.aws_s3_bucket.rag_artifacts.bucket
  # Key được truyền từ GitHub Actions
  s3_key    = var.retrieve_artifact_key

  timeout     = 30
  memory_size = 1024

  environment {
    variables = {
      KNOWLEDGE_BASE_ID = aws_bedrockagent_knowledge_base.kb.id
      REGION = var.region
    }
  }
}

# API Gateway (Cần thiết để gọi Lambda Retriever)
resource "aws_apigatewayv2_api" "rag_api" {
  name          = "${var.project}-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "retrieve_integration" {
  api_id             = aws_apigatewayv2_api.rag_api.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.retrieve.invoke_arn
  integration_method = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "default_route" {
  api_id    = aws_apigatewayv2_api.rag_api.id
  route_key = "POST /"
  target    = "integrations/${aws_apigatewayv2_integration.retrieve_integration.id}"
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.rag_api.id
  name        = "$default"
  auto_deploy = true
}

# Cho phép API Gateway gọi Lambda
resource "aws_lambda_permission" "api_gateway_permission" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.retrieve.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rag_api.execution_arn}/*/*"
}