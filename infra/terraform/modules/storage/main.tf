# S3-compatible object storage (MinIO locally, S3 here) for uploaded PDFs.
# See core/storage.py — the app talks to whatever S3_ENDPOINT_URL points at
# through the same boto3 client either way.

resource "random_id" "suffix" {
  byte_length = 4 # S3 bucket names are global; avoids collisions across accounts/envs
}

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "this" {
  description         = "${var.name} documents bucket encryption"
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
        Sid       = "AllowS3"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
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

resource "aws_s3_bucket" "documents" {
  #checkov:skip=CKV2_AWS_62:No event consumer exists -- ingestion is app-triggered (see routers/documents.py), not S3-event-triggered -- see infra/terraform/README.md
  #checkov:skip=CKV_AWS_144:No second region provisioned yet -- see infra/terraform/README.md
  bucket = "${var.name}-documents-${random_id.suffix.hex}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "documents" {
  bucket = aws_s3_bucket.documents.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.this.arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    id     = "expire-noncurrent-versions"
    status = "Enabled"
    filter {}

    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_expiration_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_logging" "documents" {
  bucket        = aws_s3_bucket.documents.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "documents-access-logs/"
}

# A dedicated logs bucket avoids the "bucket logs to itself" cycle and keeps
# access-log retention/lifecycle independent from the documents themselves.
resource "aws_s3_bucket" "access_logs" {
  #checkov:skip=CKV2_AWS_62:No event consumer exists -- see infra/terraform/README.md
  #checkov:skip=CKV_AWS_144:No second region provisioned yet -- see infra/terraform/README.md
  #checkov:skip=CKV_AWS_145:SSE-S3, not KMS: avoids extra IAM plumbing for the S3 log-delivery service account on a bucket holding only request metadata -- see infra/terraform/README.md
  bucket = "${var.name}-access-logs-${random_id.suffix.hex}"
  tags   = var.tags
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256" # SSE-S3, not KMS: the log-delivery service account can't be granted KMS key access as easily as SSE-S3
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-old-access-logs"
    status = "Enabled"
    filter {}

    expiration {
      days = 365
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_versioning" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# Deny any request that isn't TLS -- S3 allows plain HTTP by default, which
# would let the app's presigned-URL flow or a misconfigured client leak
# document contents on the wire.
resource "aws_s3_bucket_policy" "documents_require_tls" {
  bucket = aws_s3_bucket.documents.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        aws_s3_bucket.documents.arn,
        "${aws_s3_bucket.documents.arn}/*",
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}
