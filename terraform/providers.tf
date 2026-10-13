provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aws-lambda-serverless-api"
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  }
}
