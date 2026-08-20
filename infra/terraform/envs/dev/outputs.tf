output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "api_irsa_role_arn" {
  description = "Paste into infra/k8s/base/serviceaccounts.yaml's api ServiceAccount eks.amazonaws.com/role-arn annotation."
  value       = module.eks.api_role_arn
}

output "worker_irsa_role_arn" {
  description = "Paste into infra/k8s/base/serviceaccounts.yaml's worker ServiceAccount eks.amazonaws.com/role-arn annotation."
  value       = module.eks.worker_role_arn
}

output "db_migrate_irsa_role_arn" {
  description = "Paste into infra/k8s/base/serviceaccounts.yaml's db-migrate ServiceAccount eks.amazonaws.com/role-arn annotation."
  value       = module.eks.db_migrate_role_arn
}

output "rds_endpoint" {
  value = module.database.endpoint
}

output "redis_endpoint" {
  value = module.cache.primary_endpoint
}

output "documents_bucket_name" {
  value = module.storage.bucket_name
}

output "app_secrets_manager_arns" {
  description = "One per key expected in the k8s app-secrets Secret (infra/k8s/base/secret.example.yaml) -- fetch each with `aws secretsmanager get-secret-value`."
  value = {
    database_master   = module.database.master_secret_arn
    database_app_user = module.database.app_user_secret_arn
    database_app_auth = module.database.app_auth_secret_arn
    redis             = module.cache.secret_arn
    jwt_secret        = aws_secretsmanager_secret.app_jwt_secret.arn
    session_secret    = aws_secretsmanager_secret.app_session_secret.arn
    anthropic_api_key = aws_secretsmanager_secret.anthropic_api_key.arn
    openai_api_key    = aws_secretsmanager_secret.openai_api_key.arn
    gemini_api_key    = aws_secretsmanager_secret.gemini_api_key.arn
  }
}
