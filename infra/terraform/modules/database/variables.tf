variable "name" {
  description = "Prefix for all resource names/tags."
  type        = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  description = "At least 2, in different AZs (DB subnet group requirement)."
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) >= 2
    error_message = "RDS requires subnets in at least 2 availability zones."
  }
}

variable "allowed_security_group_ids" {
  description = "Security groups (api/worker/db-migrate pods) allowed to reach Postgres on 5432. Never opened beyond this — no public accessibility, no 0.0.0.0/0."
  type        = list(string)
}

variable "engine_version" {
  description = "Postgres 15.3+ is required for pgvector (see migrations/versions/c4fa907d327a_pgvector_document_chunks.py); this repo runs 16 in docker-compose/CI."
  type        = string
  default     = "16.4"
}

variable "instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "allocated_storage_gb" {
  type    = number
  default = 50
}

variable "max_allocated_storage_gb" {
  description = "Ceiling for RDS storage autoscaling."
  type        = number
  default     = 200
}

variable "multi_az" {
  description = "Standby replica in a second AZ for automatic failover. Off by default (cost) — turn on for anything with an uptime expectation."
  type        = bool
  default     = false
}

variable "backup_retention_days" {
  type    = number
  default = 14
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "skip_final_snapshot" {
  description = "Only ever true for a throwaway/dev environment being torn down for good."
  type        = bool
  default     = false
}

variable "database_name" {
  type    = string
  default = "knowledge_platform"
}

variable "tags" {
  type    = map(string)
  default = {}
}
