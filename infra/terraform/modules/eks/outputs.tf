output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "cluster_security_group_id" {
  value = aws_security_group.cluster.id
}

output "node_security_group_id" {
  # EKS auto-creates a "cluster security group" it also attaches to nodes;
  # aws_security_group.cluster covers node<->control-plane traffic, which is
  # what api/worker/db-migrate's SG rules (network module's callers) need to
  # allow egress from.
  value = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
}

output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.this.arn
}

output "api_role_arn" {
  value = aws_iam_role.api.arn
}

output "worker_role_arn" {
  value = aws_iam_role.worker.arn
}

output "db_migrate_role_arn" {
  value = aws_iam_role.db_migrate.arn
}
