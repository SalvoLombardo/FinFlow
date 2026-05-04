output "api_gateway_url" {
  description = "HTTP API invoke URL — set as backend URL in frontend build"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "api_lambda_arn" {
  value = aws_lambda_function.api.arn
}

output "api_lambda_name" {
  value = aws_lambda_function.api.function_name
}

output "projection_consumer_lambda_name" {
  value = aws_lambda_function.projection_consumer.function_name
}

output "ai_consumer_lambda_name" {
  value = aws_lambda_function.ai_consumer.function_name
}

output "notification_consumer_lambda_name" {
  value = aws_lambda_function.notification_consumer.function_name
}
