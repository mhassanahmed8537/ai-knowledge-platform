variable "name" {
  type = string
}

variable "noncurrent_version_expiration_days" {
  description = "How long to keep old versions of a document after it's replaced/deleted before S3 expires them."
  type        = number
  default     = 90
}

variable "tags" {
  type    = map(string)
  default = {}
}
