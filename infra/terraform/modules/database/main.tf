resource "aws_db_subnet_group" "this" {
  name       = "${var.name}-db"
  subnet_ids = var.private_subnet_ids
  tags       = var.tags
}

resource "aws_security_group" "this" {
  name_prefix = "${var.name}-db-"
  description = "RDS Postgres: ingress from api/worker/db-migrate pods only"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-db" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  for_each                     = toset(var.allowed_security_group_ids)
  security_group_id            = aws_security_group.this.id
  referenced_security_group_id = each.value
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "Postgres from an app security group"
}

# RDS doesn't need to initiate outbound traffic; no egress rule means none is
# allowed (the security group resource itself carries no implicit default).

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "storage" {
  description         = "${var.name} RDS storage + Secrets Manager encryption"
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

# RDS enhanced monitoring (CKV_AWS_118) needs its own role -- the managed
# policy below is AWS's own, scoped to exactly what the monitoring agent
# needs (PutMetricData/CreateLogGroup/PutLogEvents), nothing broader.
resource "aws_iam_role" "rds_monitoring" {
  name = "${var.name}-rds-monitoring"
  tags = var.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# log_statement=ddl gives an audit trail of schema changes (who ran what
# migration, when) without the volume/cost of logging every row-level query;
# slow queries still get flagged via min_duration.
resource "aws_db_parameter_group" "this" {
  name   = "${var.name}-postgres"
  family = "postgres${split(".", var.engine_version)[0]}"
  tags   = var.tags

  parameter {
    name  = "log_statement"
    value = "ddl"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }

  parameter {
    name  = "rds.force_ssl"
    value = "1"
  }
}

# --- Master (superuser) credential: only ever used by the migration Job's
# MIGRATION_DATABASE_URL, never by api/worker. ---

resource "random_password" "master" {
  length  = 32
  special = false # simplifies safe embedding in connection strings / DDL — see scripts/prepare_db.py's _quoted_password
}

resource "aws_secretsmanager_secret" "master" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda (RDS/ElastiCache templates or custom) -- see infra/terraform/README.md
  name                    = "${var.name}/rds/master"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.storage.arn
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "master" {
  secret_id = aws_secretsmanager_secret.master.id
  secret_string = jsonencode({
    username = "postgres"
    password = random_password.master.result
    url      = "postgresql+asyncpg://postgres:${random_password.master.result}@${aws_db_instance.this.address}:5432/${var.database_name}"
  })
}

# --- app_user / app_auth: least-privilege runtime roles. The roles
# themselves are created by the migration Job (scripts/prepare_db.py),
# which reads APP_USER_PASSWORD / APP_AUTH_PASSWORD from these secrets —
# Terraform generates and stores the values, it doesn't touch Postgres
# directly (this module has no Postgres provider dependency, deliberately,
# to keep `terraform plan` usable without live DB connectivity). ---

resource "random_password" "app_user" {
  length  = 32
  special = false
}

resource "random_password" "app_auth" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "app_user" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda (RDS/ElastiCache templates or custom) -- see infra/terraform/README.md
  name                    = "${var.name}/rds/app_user"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.storage.arn
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "app_user" {
  secret_id = aws_secretsmanager_secret.app_user.id
  secret_string = jsonencode({
    username = "app_user"
    password = random_password.app_user.result
    url      = "postgresql+asyncpg://app_user:${random_password.app_user.result}@${aws_db_instance.this.address}:5432/${var.database_name}"
  })
}

resource "aws_secretsmanager_secret" "app_auth" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda (RDS/ElastiCache templates or custom) -- see infra/terraform/README.md
  name                    = "${var.name}/rds/app_auth"
  recovery_window_in_days = 7
  kms_key_id              = aws_kms_key.storage.arn
  tags                    = var.tags
}

resource "aws_secretsmanager_secret_version" "app_auth" {
  secret_id = aws_secretsmanager_secret.app_auth.id
  secret_string = jsonencode({
    username = "app_auth"
    password = random_password.app_auth.result
    url      = "postgresql+asyncpg://app_auth:${random_password.app_auth.result}@${aws_db_instance.this.address}:5432/${var.database_name}"
  })
}

resource "aws_db_instance" "this" {
  #checkov:skip=CKV_AWS_157:Multi-AZ is env-configurable via var.multi_az (default false for cost) -- see infra/terraform/README.md
  identifier     = var.name
  engine         = "postgres"
  engine_version = var.engine_version
  instance_class = var.instance_class

  db_name  = var.database_name
  username = "postgres"
  password = random_password.master.result
  port     = 5432

  allocated_storage     = var.allocated_storage_gb
  max_allocated_storage = var.max_allocated_storage_gb
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.storage.arn

  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name
  vpc_security_group_ids = [aws_security_group.this.id]
  publicly_accessible    = false

  # Not adopted end-to-end yet — api/worker still authenticate with the
  # Secrets Manager passwords above — but enabling it now means the app can
  # move to short-lived IAM auth tokens later without a DB instance
  # replacement. See db_bootstrap.sql's header comment for the same intent.
  iam_database_authentication_enabled = true

  multi_az                   = var.multi_az
  backup_retention_period    = var.backup_retention_days
  auto_minor_version_upgrade = true
  deletion_protection        = var.deletion_protection
  skip_final_snapshot        = var.skip_final_snapshot
  final_snapshot_identifier  = var.skip_final_snapshot ? null : "${var.name}-final"

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.storage.arn
  monitoring_interval             = 60
  monitoring_role_arn             = aws_iam_role.rds_monitoring.arn

  copy_tags_to_snapshot = true
  tags                  = var.tags

  lifecycle {
    # Rotation replaces the value in Secrets Manager; RDS is updated out of
    # band (or by the migration Job re-running ALTER ROLE for app_user/
    # app_auth). Terraform re-asserting the *original* random_password value
    # here on every plan would fight that.
    ignore_changes = [password]
  }
}
