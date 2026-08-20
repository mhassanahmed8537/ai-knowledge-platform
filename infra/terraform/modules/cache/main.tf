resource "aws_elasticache_subnet_group" "this" {
  name       = "${var.name}-redis"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name_prefix = "${var.name}-redis-"
  description = "ElastiCache Redis: ingress from api/worker pods only"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-redis" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "redis" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  description                  = "Redis from an app security group"
}

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "this" {
  description         = "${var.name} ElastiCache Redis (at-rest + Secrets Manager encryption)"
  enable_key_rotation = true
  tags                = var.tags

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AccountRootFullAccess"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        Sid       = "AllowSecretsManager"
        Effect    = "Allow"
        Principal = { Service = "secretsmanager.amazonaws.com" }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
      },
    ]
  })
}

# AUTH token: Redis's equivalent of a password. Alphanumeric-only (no `special`)
# because it's embedded directly in REDIS_URL / CELERY_BROKER_URL, same
# reasoning as the RDS passwords in modules/database.
resource "random_password" "auth_token" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "redis" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda (RDS/ElastiCache templates or custom) -- see infra/terraform/README.md
  name                    = "${var.name}/redis/auth-token"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.this.arn
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "redis" {
  secret_id = aws_secretsmanager_secret.redis.id
  secret_string = jsonencode({
    auth_token = random_password.auth_token.result
    url        = "rediss://:${random_password.auth_token.result}@${aws_elasticache_replication_group.this.primary_endpoint_address}:6379/0"
  })
}

resource "aws_elasticache_replication_group" "this" {
  #checkov:skip=CKV2_AWS_50:Multi-AZ is env-configurable via var.num_cache_clusters (default 1 for cost) -- see infra/terraform/README.md
  replication_group_id = var.name
  description          = "${var.name} Redis (cache + Celery broker)"

  engine         = "redis"
  engine_version = var.engine_version
  node_type      = var.node_type
  port           = 6379

  num_cache_clusters         = var.num_cache_clusters
  automatic_failover_enabled = var.num_cache_clusters > 1
  multi_az_enabled           = var.num_cache_clusters > 1

  subnet_group_name  = aws_elasticache_subnet_group.this.name
  security_group_ids = [aws_security_group.this.id]

  at_rest_encryption_enabled = true
  kms_key_id                 = aws_kms_key.this.arn
  transit_encryption_enabled = true
  auth_token                 = random_password.auth_token.result

  snapshot_retention_limit   = var.snapshot_retention_days
  auto_minor_version_upgrade = true

  tags = var.tags

  lifecycle {
    ignore_changes = [auth_token] # rotated out of band, see modules/database's aws_db_instance for the same reasoning
  }
}
