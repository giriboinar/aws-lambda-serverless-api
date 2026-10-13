variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Environment name used in resource names and tags."
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Base name for resources."
  type        = string
  default     = "tasks-api"
}

variable "log_retention_days" {
  description = "CloudWatch log retention for the Lambda function."
  type        = number
  default     = 14
}
