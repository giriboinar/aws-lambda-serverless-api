output "api_endpoint" {
  description = "Base URL of the HTTP API."
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "lambda_function_name" {
  description = "Deployed Lambda function name."
  value       = aws_lambda_function.api.function_name
}

output "dynamodb_table_name" {
  description = "DynamoDB table name."
  value       = aws_dynamodb_table.tasks.name
}
