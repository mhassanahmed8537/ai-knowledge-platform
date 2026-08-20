variable "name" {
  description = "Prefix for all resource names/tags (e.g. \"knowledge-platform-dev\")."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.20.0.0/16"
}

variable "azs" {
  description = "Availability zones to spread subnets across. Needs at least 2 for RDS/ElastiCache subnet groups and EKS control-plane HA."
  type        = list(string)

  validation {
    condition     = length(var.azs) >= 2
    error_message = "At least 2 availability zones are required."
  }
}

variable "single_nat_gateway" {
  description = "Use one NAT gateway for all private subnets instead of one per AZ. Cheaper (~$32/mo vs one per AZ) at the cost of a single point of failure for private-subnet egress — fine for dev, not recommended once an environment matters enough to page someone."
  type        = bool
  default     = true
}

variable "flow_log_retention_days" {
  description = "CloudWatch Logs retention for VPC flow logs. Defaults to a year for incident-response usefulness; lower it for a throwaway dev environment if the cost isn't worth it."
  type        = number
  default     = 365
}

variable "tags" {
  description = "Tags applied to every resource this module creates."
  type        = map(string)
  default     = {}
}
