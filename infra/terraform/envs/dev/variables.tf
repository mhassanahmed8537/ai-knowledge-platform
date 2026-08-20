variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "azs" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "environment" {
  type    = string
  default = "dev"
}

variable "k8s_namespace" {
  description = "Must match infra/k8s/overlays/dev/kustomization.yaml's `namespace:` field."
  type        = string
  default     = "knowledge-platform-dev"
}
