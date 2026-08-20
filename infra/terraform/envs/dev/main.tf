locals {
  name = "knowledge-platform-${var.environment}"
  tags = {
    Project     = "ai-knowledge-platform"
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

module "network" {
  source = "../../modules/network"

  name               = local.name
  azs                = var.azs
  single_nat_gateway = true # dev: cost over cross-AZ NAT redundancy -- see the module's own variable doc
  tags               = local.tags
}

module "eks" {
  source = "../../modules/eks"

  name                = local.name
  namespace           = var.k8s_namespace
  vpc_id              = module.network.vpc_id
  private_subnet_ids  = module.network.private_subnet_ids
  node_desired_size   = 2
  node_min_size       = 2
  node_max_size       = 4
  node_instance_types = ["t3.large"]

  app_bucket_arn         = module.storage.bucket_arn
  app_bucket_kms_key_arn = module.storage.kms_key_arn
  app_secret_arns = [
    module.database.app_user_secret_arn,
    module.database.app_auth_secret_arn,
    module.cache.secret_arn,
    aws_secretsmanager_secret.anthropic_api_key.arn,
    aws_secretsmanager_secret.openai_api_key.arn,
    aws_secretsmanager_secret.gemini_api_key.arn,
    aws_secretsmanager_secret.app_jwt_secret.arn,
    aws_secretsmanager_secret.app_session_secret.arn,
  ]
  migration_secret_arns = [
    module.database.master_secret_arn,
    module.database.app_user_secret_arn,
    module.database.app_auth_secret_arn,
  ]

  tags = local.tags
}

module "database" {
  source = "../../modules/database"

  name                       = local.name
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.eks.node_security_group_id]
  multi_az                   = false # dev; flip on for anything with an uptime expectation
  deletion_protection        = false # dev; a throwaway environment shouldn't need `terraform destroy` fought
  skip_final_snapshot        = true
  tags                       = local.tags
}

module "cache" {
  source = "../../modules/cache"

  name                       = local.name
  vpc_id                     = module.network.vpc_id
  private_subnet_ids         = module.network.private_subnet_ids
  allowed_security_group_ids = [module.eks.node_security_group_id]
  num_cache_clusters         = 1 # dev; 2+ for automatic failover
  tags                       = local.tags
}

module "storage" {
  source = "../../modules/storage"

  name = local.name
  tags = local.tags
}

# --- Secret containers for values Terraform can't generate itself (real
# vendor API keys) -- created empty, populated out of band:
#   aws secretsmanager put-secret-value --secret-id <arn> --secret-string '{"api_key":"sk-..."}'
# Terraform owns the container (encryption, IAM access boundary via
# app_secret_arns above), never the plaintext value. ---

resource "aws_secretsmanager_secret" "anthropic_api_key" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda -- see infra/terraform/README.md
  name                    = "${local.name}/llm/anthropic-api-key"
  recovery_window_in_days = 7
  kms_key_id              = module.storage.kms_key_arn
  tags                    = local.tags
}

resource "aws_secretsmanager_secret" "openai_api_key" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda -- see infra/terraform/README.md
  name                    = "${local.name}/llm/openai-api-key"
  recovery_window_in_days = 7
  kms_key_id              = module.storage.kms_key_arn
  tags                    = local.tags
}

resource "aws_secretsmanager_secret" "gemini_api_key" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda -- see infra/terraform/README.md
  name                    = "${local.name}/llm/gemini-api-key"
  recovery_window_in_days = 7
  kms_key_id              = module.storage.kms_key_arn
  tags                    = local.tags
}

# JWT_SECRET / SESSION_SECRET: api/main.py's _check_production_secrets()
# refuses to start outside ENVIRONMENT=local with the dev-default values, so
# these have to be real generated secrets before the api Deployment
# rolls out.
resource "random_password" "app_jwt_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "app_jwt_secret" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda -- see infra/terraform/README.md
  name                    = "${local.name}/app/jwt-secret"
  recovery_window_in_days = 7
  kms_key_id              = module.storage.kms_key_arn
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "app_jwt_secret" {
  secret_id     = aws_secretsmanager_secret.app_jwt_secret.id
  secret_string = jsonencode({ JWT_SECRET = random_password.app_jwt_secret.result })
}

resource "random_password" "app_session_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "app_session_secret" {
  #checkov:skip=CKV2_AWS_57:Rotation needs a Lambda -- see infra/terraform/README.md
  name                    = "${local.name}/app/session-secret"
  recovery_window_in_days = 7
  kms_key_id              = module.storage.kms_key_arn
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "app_session_secret" {
  secret_id     = aws_secretsmanager_secret.app_session_secret.id
  secret_string = jsonencode({ SESSION_SECRET = random_password.app_session_secret.result })
}
