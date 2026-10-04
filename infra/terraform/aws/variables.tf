variable "project" {
  type    = string
  default = "policy-analytics"
}

variable "region" {
  type    = string
  default = "ap-southeast-1"
}

variable "github_repo" {
  description = "owner/repo allowed to deploy through GitHub OIDC, e.g. weikiat98/policy-analytics"
  type        = string
  default     = "REPLACE_ME/REPLACE_ME"
}

variable "alert_email" {
  description = "Email for AWS Budgets alerts"
  type        = string
  default     = "REPLACE_ME@example.com"
}

variable "monthly_budget_usd" {
  type    = number
  default = 30
}

variable "image_tag" {
  description = "Initial image tag for the ECS task definitions (later revisions come from the deploy pipeline)"
  type        = string
  default     = "bootstrap"
}

variable "langfuse_host" {
  type    = string
  default = "https://cloud.langfuse.com"
}
