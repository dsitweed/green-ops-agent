variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "aws-finops-agent"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]*$", var.project_name))
    error_message = "Project name must start with a lowercase letter and can only contain lowercase letters, numbers, and hyphens."
  }
}

variable "aws_region" {
  description = "The AWS region to deploy resources in"
  type        = string
  default     = "ap-northeast-1"
}

variable "aws_profile" {
  description = "The AWS CLI profile for data collection account"
  type        = string
  default     = ""
}

variable "environment" {
  description = "The environment for the resources (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "tags" {
  description = "A map of tags to apply to all resources"
  type        = map(string)
  default     = {}
}

locals {
  common_tags = merge(
    var.tags,
    {
      Name        = "${var.project_name}-${var.environment}"
      Project     = var.project_name
      ManagedBy   = "terraform"
      Environment = var.environment
    }
  )
}

data "aws_caller_identity" "current" {}

data "aws_vpc" "current" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.current.id]
  }

  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical account ID for Ubuntu

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}
