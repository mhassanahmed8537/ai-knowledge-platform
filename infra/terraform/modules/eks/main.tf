data "aws_caller_identity" "current" {}

# --- Cluster ---

resource "aws_kms_key" "cluster" {
  description         = "${var.name} EKS secrets envelope encryption + control-plane log group"
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
        Sid       = "AllowEksSecretsEnvelope"
        Effect    = "Allow"
        Principal = { AWS = aws_iam_role.cluster.arn }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
      },
      {
        Sid       = "AllowCloudWatchLogs"
        Effect    = "Allow"
        Principal = { Service = "logs.${data.aws_region.current.name}.amazonaws.com" }
        Action = [
          "kms:Encrypt*",
          "kms:Decrypt*",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:Describe*",
        ]
        Resource = "*"
      },
    ]
  })
}

data "aws_region" "current" {}

resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${var.name}/cluster"
  retention_in_days = var.control_plane_log_retention_days
  kms_key_id        = aws_kms_key.cluster.arn
  tags              = var.tags
}

resource "aws_security_group" "cluster" {
  name_prefix = "${var.name}-eks-cluster-"
  description = "EKS control plane <-> node communication"
  vpc_id      = var.vpc_id
  tags        = merge(var.tags, { Name = "${var.name}-eks-cluster" })

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_iam_role" "cluster" {
  name = "${var.name}-eks-cluster"
  tags = var.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_eks_cluster" "this" {
  #checkov:skip=CKV_AWS_38:public_access_cidrs is env-configurable (default 0.0.0.0/0 so the module works before a VPN/office CIDR exists); endpoint_private_access is also on -- see infra/terraform/README.md
  #checkov:skip=CKV_AWS_39:Same as CKV_AWS_38 -- public endpoint is deliberately available, scoped by public_access_cidrs -- see infra/terraform/README.md
  name     = var.name
  role_arn = aws_iam_role.cluster.arn
  version  = var.kubernetes_version
  tags     = var.tags

  vpc_config {
    subnet_ids              = var.private_subnet_ids
    security_group_ids      = [aws_security_group.cluster.id]
    endpoint_public_access  = true
    endpoint_private_access = true
    public_access_cidrs     = var.public_access_cidrs
  }

  encryption_config {
    provider {
      key_arn = aws_kms_key.cluster.arn
    }
    resources = ["secrets"]
  }

  # All five log types: this is the audit trail for "who called the k8s API
  # and did what," which matters a lot more than its CloudWatch cost.
  enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  depends_on = [
    aws_iam_role_policy_attachment.cluster,
    aws_cloudwatch_log_group.cluster,
  ]
}

# --- IRSA: lets k8s ServiceAccounts assume IAM roles without static AWS
# credentials anywhere in a pod. See infra/k8s/base/serviceaccounts.yaml for
# the annotations that reference the role ARNs this outputs. ---

data "tls_certificate" "oidc" {
  url = aws_eks_cluster.this.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "this" {
  url             = aws_eks_cluster.this.identity[0].oidc[0].issuer
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.oidc.certificates[0].sha1_fingerprint]
  tags            = var.tags
}

locals {
  oidc_provider_url = replace(aws_iam_openid_connect_provider.this.url, "https://", "")
}

# --- Managed node group ---

resource "aws_iam_role" "node" {
  name = "${var.name}-eks-node"
  tags = var.tags

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "node_worker" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
}

resource "aws_iam_role_policy_attachment" "node_cni" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
}

resource "aws_iam_role_policy_attachment" "node_ecr" {
  role       = aws_iam_role.node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_eks_node_group" "default" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "${var.name}-default"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = var.private_subnet_ids
  instance_types  = var.node_instance_types
  capacity_type   = var.node_capacity_type
  tags            = var.tags

  scaling_config {
    desired_size = var.node_desired_size
    min_size     = var.node_min_size
    max_size     = var.node_max_size
  }

  update_config {
    max_unavailable = 1
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
  ]
}
