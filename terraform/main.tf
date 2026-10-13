# ── Lambda deployment package ────────────────────────────────────────────
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda.zip"
}

# ── DynamoDB table (on-demand; tiny demo usage stays in Free Tier) ──────────
resource "aws_dynamodb_table" "tasks" {
  name         = "${var.project_name}-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# ── IAM: least-privilege execution role for the Lambda function ──────────────
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_exec" {
  name               = "${var.project_name}-${var.environment}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda_policy" {
  # CloudWatch Logs: write-only to this function's log group.
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]
    resources = ["arn:aws:logs:${var.aws_region}:*:log-group:/aws/lambda/${var.project_name}-${var.environment}:*"]
  }

  # DynamoDB: only the operations the API needs, only on this table.
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:PutItem",
      "dynamodb:DeleteItem",
      "dynamodb:Scan",
    ]
    resources = [aws_dynamodb_table.tasks.arn]
  }
}

resource "aws_iam_role_policy" "lambda_policy" {
  name   = "${var.project_name}-${var.environment}-policy"
  role   = aws_iam_role.lambda_exec.id
  policy = data.aws_iam_policy_document.lambda_policy.json
}

# ── CloudWatch log group (explicit retention, avoids infinite retention) ─────
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
}

# ── Lambda function ──────────────────────────────────────────────────────────
resource "aws_lambda_function" "api" {
  function_name    = "${var.project_name}-${var.environment}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "handler.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      TASKS_TABLE = aws_dynamodb_table.tasks.name
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

# ── API Gateway HTTP API ─────────────────────────────────────────────────────
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.project_name}-${var.environment}"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "routes" {
  for_each  = toset(["GET /health", "GET /tasks", "POST /tasks", "GET /tasks/{id}", "DELETE /tasks/{id}"])
  api_id    = aws_apigatewayv2_api.api.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api.arn
    format          = "$context.requestId $context.httpMethod $context.path $context.status"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/apigateway/${var.project_name}-${var.environment}"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
