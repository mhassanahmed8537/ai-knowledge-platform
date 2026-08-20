variable "name" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "allowed_security_group_ids" {
  description = "Security groups (api/worker pods) allowed to reach Redis on 6379."
  type        = list(string)
}

variable "node_type" {
  type    = string
  default = "cache.t4g.small"
}

variable "num_cache_clusters" {
  description = "1 primary + N-1 read replicas. 2 gives automatic failover; 1 is single-node (dev/cost-sensitive only — no HA)."
  type        = number
  default     = 1
}

variable "engine_version" {
  type    = string
  default = "7.1"
}

variable "snapshot_retention_days" {
  type    = number
  default = 7
}

variable "tags" {
  type    = map(string)
  default = {}
}
