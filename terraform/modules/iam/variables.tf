variable "name" {
  type = string
}

variable "github_repository" {
  type        = string
  description = "GitHub repository in owner/repo format"
}

variable "ecr_repository_arn" {
  type = string
}
