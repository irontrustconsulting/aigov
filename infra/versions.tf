# Terraform + provider version pins.
#
# Pinning means `terraform init` resolves the SAME provider versions on every
# machine, so an apply on your laptop matches an apply in CI or on a teammate's
# machine later — no "works on mine" drift. This is the reproducibility we were
# after when we chose IaC over the console.

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0" # any 5.x, but not 6.0 (a major bump may break things)
    }
  }
}

# The AWS provider authenticates using your NORMAL AWS credential chain
# (env vars, ~/.aws/credentials, or SSO) — the same credentials the AWS CLI
# uses. Terraform never stores AWS credentials in these files.
provider "aws" {
  region = var.aws_region
}
