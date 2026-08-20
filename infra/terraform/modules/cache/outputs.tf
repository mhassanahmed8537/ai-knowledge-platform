output "primary_endpoint" {
  value = aws_elasticache_replication_group.this.primary_endpoint_address
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "secret_arn" {
  value = aws_secretsmanager_secret.redis.arn
}
