# IRSA: one IAM role per ServiceAccount (infra/k8s/base/serviceaccounts.yaml),
# each trusting *only* its own namespace:serviceaccount subject via the
# cluster's OIDC provider -- a pod running as the `worker` ServiceAccount
# cannot assume the `db-migrate` role, even though both trust the same OIDC
# provider, because the `sub` claim condition below is per-role.

data "aws_iam_policy_document" "irsa_trust" {
  for_each = toset(["api", "worker", "db-migrate"])

  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.this.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:sub"
      values   = ["system:serviceaccount:${var.namespace}:${each.value}"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider_url}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "api" {
  name               = "${var.name}-irsa-api"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["api"].json
  tags               = var.tags
}

resource "aws_iam_role" "worker" {
  name               = "${var.name}-irsa-worker"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["worker"].json
  tags               = var.tags
}

resource "aws_iam_role" "db_migrate" {
  name               = "${var.name}-irsa-db-migrate"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust["db-migrate"].json
  tags               = var.tags
}

# api: reads Secrets Manager (its own DB/Redis/LLM creds) and can read/write
# the documents bucket -- uploads land there directly from the request
# handler (see services/api/src/api/routers/documents.py's upload_document).
data "aws_iam_policy_document" "api" {
  statement {
    sid       = "ReadAppSecrets"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.app_secret_arns
  }

  statement {
    sid    = "DocumentsBucketReadWrite"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]
    resources = ["${var.app_bucket_arn}/*"]
  }

  statement {
    sid       = "DocumentsBucketList"
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [var.app_bucket_arn]
  }

  statement {
    sid    = "BucketKmsUse"
    effect = "Allow"
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]
    resources = [var.app_bucket_kms_key_arn]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "${var.name}-irsa-api"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

# worker: same secrets + bucket access as api (it's the side that actually
# runs the download -> extract -> chunk -> embed -> upload-back-if-needed
# pipeline in core/ingestion.py), identical policy shape.
resource "aws_iam_role_policy" "worker" {
  name   = "${var.name}-irsa-worker"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.api.json
}

# db-migrate: only Secrets Manager, only the migration-specific secrets
# (RDS master credential, plus app_user/app_auth so scripts/prepare_db.py
# can set their passwords) -- never the documents bucket, never app_secret_arns.
data "aws_iam_policy_document" "db_migrate" {
  statement {
    sid       = "ReadMigrationSecrets"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.migration_secret_arns
  }
}

resource "aws_iam_role_policy" "db_migrate" {
  name   = "${var.name}-irsa-db-migrate"
  role   = aws_iam_role.db_migrate.id
  policy = data.aws_iam_policy_document.db_migrate.json
}
