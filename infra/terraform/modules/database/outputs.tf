output "endpoint" {
  value = aws_db_instance.this.address
}

output "security_group_id" {
  value = aws_security_group.this.id
}

output "master_secret_arn" {
  value = aws_secretsmanager_secret.master.arn
}

output "app_user_secret_arn" {
  value = aws_secretsmanager_secret.app_user.arn
}

output "app_auth_secret_arn" {
  value = aws_secretsmanager_secret.app_auth.arn
}
