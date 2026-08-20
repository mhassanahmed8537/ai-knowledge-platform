# Terraform

`modules/` (network, database, cache, storage, eks) + `envs/dev` wiring them
together — production-correct AWS infrastructure for the platform described
in the repo root README, validated via `fmt`/`checkov`, not continuously
deployed (see that README's "Infra" row).

## Layout

```
modules/
  network/    VPC, public/private subnets, NAT, VPC flow logs
  database/   RDS Postgres (pgvector-capable, 15.3+), app_user/app_auth/
              master credentials in Secrets Manager
  cache/      ElastiCache Redis (cache + Celery broker), AUTH token in
              Secrets Manager
  storage/    S3 documents bucket + access-log bucket, KMS, TLS-only policy
  eks/        EKS cluster, managed node group, OIDC provider + IRSA roles
              for api/worker/db-migrate (matches infra/k8s ServiceAccounts)
envs/dev/     wires the above together with dev-sized defaults
```

## Validating

`terraform validate`/`plan` need the `hashicorp/aws` provider plugin from
`registry.terraform.io`, which this session's egress policy blocks (a 403 at
the proxy, not a transient failure — confirmed via `terraform init` and not
routed around, per this environment's own instructions not to bypass policy
denials). Validation here instead used:

```bash
terraform fmt -check -recursive          # syntax + canonical formatting
checkov -d . --framework terraform       # static HCL analysis — no
                                          # provider plugin needed, so this
                                          # ran clean and caught real issues
                                          # (fixed as they were found; see below)
```

Run `terraform init && terraform validate && terraform plan` yourself
somewhere with registry access before ever applying — `fmt`/`checkov` catch
syntax and security-posture issues, not type errors against the actual
provider schema.

## Deploying (once validated with real `init`/`plan`)

```bash
cd envs/dev
terraform init   # after pointing versions.tf's backend "s3" block at a real bucket
terraform apply

# Wire the outputs into infra/k8s:
terraform output api_irsa_role_arn        # -> serviceaccounts.yaml's api annotation
terraform output worker_irsa_role_arn     # -> serviceaccounts.yaml's worker annotation
terraform output db_migrate_irsa_role_arn # -> serviceaccounts.yaml's db-migrate annotation
terraform output app_secrets_manager_arns # -> fetch each, populate infra/k8s's
                                           #    app-secrets / db-migrate-secret
```

## Security posture: accepted / deferred trade-offs

Surfaced by `checkov`, deliberately not "fixed" — same philosophy as
`infra/k8s/README.md`: the reasoning lives next to the decision rather than
being silently suppressed.

- **Multi-AZ (RDS `var.multi_az`, ElastiCache `var.num_cache_clusters`).**
  Both default to single-node/single-AZ for cost; flip them on per
  environment once uptime matters enough to page someone. `envs/dev` passes
  the same defaults explicitly.
- **EKS public endpoint (`CKV_AWS_38`/`39`).** `endpoint_public_access = true`
  with `public_access_cidrs` defaulting to `0.0.0.0/0` — the module needs to
  work before a VPN/office CIDR necessarily exists. Set
  `public_access_cidrs` per environment once one does;
  `endpoint_private_access` is also on, so in-VPC traffic never needs the
  public path regardless.
- **Secrets Manager rotation (`CKV2_AWS_57`, all secrets).** Automatic
  rotation needs a Lambda (AWS's own RDS/ElastiCache rotation templates, or
  a custom one) plus its own VPC networking and IAM — a real feature, not a
  one-line fix. Interim story: re-run `terraform apply -replace` on the
  relevant `random_password` resource, then re-run the migration Job so
  `scripts/prepare_db.py` applies the new value to the Postgres roles.
- **S3 cross-region replication / event notifications (`CKV_AWS_144`,
  `CKV2_AWS_62`).** No second region and no consumer for bucket events exist
  yet — ingestion is triggered by the app enqueueing a Celery task after
  upload (see `services/api/src/api/routers/documents.py`), not by S3
  events, so wiring notifications would have nothing listening on the other
  end.
- **Access-log bucket uses SSE-S3, not KMS (`CKV_AWS_145`).** The documents
  bucket itself is KMS-encrypted; its logging destination uses SSE-S3
  because granting the S3 log-delivery service account KMS key access needs
  extra policy plumbing that isn't worth it for request metadata (no
  document contents ever land in access logs).
