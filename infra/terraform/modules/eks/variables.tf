variable "name" {
  type = string
}

variable "namespace" {
  description = "k8s namespace the app's ServiceAccounts live in (must match infra/k8s/overlays/<env>'s `namespace:` field) -- IRSA trust policies are scoped to namespace:serviceaccount, so this has to match exactly or AssumeRoleWithWebIdentity is denied."
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "EKS nodes and pods only ever run in private subnets — see infra/k8s's NetworkPolicy for the pod-level half of this."
  type        = list(string)
}

variable "kubernetes_version" {
  type    = string
  default = "1.31"
}

variable "node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}

variable "node_desired_size" {
  type    = number
  default = 3
}

variable "node_min_size" {
  type    = number
  default = 2
}

variable "node_max_size" {
  type    = number
  default = 6
}

variable "node_capacity_type" {
  description = "ON_DEMAND or SPOT. SPOT is cheaper but nodes can be reclaimed with 2 minutes' notice — fine once PodDisruptionBudgets exist (they do, see infra/k8s), risky before that."
  type        = string
  default     = "ON_DEMAND"
}

variable "control_plane_log_retention_days" {
  type    = number
  default = 365
}

variable "public_access_cidrs" {
  description = "CIDRs allowed to reach the EKS API's public endpoint. Defaults wide open so the module is usable before a VPN/office CIDR exists; tighten this per environment once one does — see the module's own note next to endpoint_public_access."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "app_bucket_arn" {
  description = "The documents S3 bucket ARN (modules/storage's output), scoped into the api/worker IRSA policies."
  type        = string
}

variable "app_bucket_kms_key_arn" {
  type = string
}

variable "app_secret_arns" {
  description = "Secrets Manager ARNs api/worker are allowed to read (RDS app_user/app_auth, Redis auth token, LLM API keys, etc.)."
  type        = list(string)
}

variable "migration_secret_arns" {
  description = "Secrets Manager ARNs only the db-migrate role can read (RDS master credential, app_user/app_auth so it can set their passwords)."
  type        = list(string)
}

variable "tags" {
  type    = map(string)
  default = {}
}
