terraform {
  required_version = ">= 1.9"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Not wired to a real bucket -- this repo's IaC is validated via
  # fmt/validate/plan-against-a-throwaway-account and kind, not continuously
  # deployed (see the root README's "Infra" row). Point this at a real,
  # versioned, encrypted S3 bucket + DynamoDB lock table before ever running
  # `terraform apply` against a real account.
  backend "s3" {
    bucket         = "REPLACE-with-a-real-tfstate-bucket"
    key            = "knowledge-platform/dev/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "REPLACE-with-a-real-lock-table"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.tags
  }
}
