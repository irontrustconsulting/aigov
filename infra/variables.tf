# Inputs to this module.
#
# Keeping region and environment as variables (rather than hardcoding them) is
# exactly what lets the SAME code stand up a dev pool today and a prod pool
# later: you change the input value, not the code. That is the whole argument
# for IaC, expressed in two variables.

variable "aws_region" {
  description = "AWS region for the operator Cognito pool."
  type        = string
  default     = "eu-west-2" # matches your existing s3_region
}

variable "environment" {
  description = "Deployment environment. Becomes part of resource names so the dev / staging / prod pools never collide."
  type        = string
  default     = "dev"
}
