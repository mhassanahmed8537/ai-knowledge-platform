# Kubernetes manifests

Kustomize `base/` + `overlays/{dev,...}`, validated with `kubectl kustomize`
(renders), [`kubeconform`](https://github.com/yannh/kubeconform) (schema),
and [`checkov`](https://www.checkov.io/) (security posture) — not
continuously deployed; see the repo root README's "Infra" row.

## Layout

```
base/
  serviceaccounts.yaml   api / worker / db-migrate — separate identities so
                          their IRSA policies (infra/terraform/modules/eks)
                          can be scoped independently
  configmap.yaml          non-secret settings
  secret.example.yaml     documents the expected Secret keys; NOT applied
                          (excluded from kustomization.yaml on purpose)
  api-deployment.yaml      + PodDisruptionBudget + HorizontalPodAutoscaler
  api-service.yaml
  worker-deployment.yaml   + PodDisruptionBudget + HorizontalPodAutoscaler
  migration-job.yaml      applied standalone (see its own header comment)
  networkpolicy.yaml       default-deny + explicit allows
  ingress.yaml             placeholder host/TLS — overlays patch these
overlays/dev/
  namespace.yaml, kustomization.yaml, and small patches (replica count,
  HPA floor, dev-profile ConfigMap values, ingress host)
```

## Deploying

```bash
# 1. Roles/secrets/creds first (see secret.example.yaml's header for the
#    kubectl create secret form, or wire up External Secrets Operator).
kubectl apply -f infra/k8s/overlays/dev/namespace.yaml
kubectl create secret generic app-secrets -n knowledge-platform-dev --from-literal=...
kubectl create secret generic db-migrate-secret -n knowledge-platform-dev --from-literal=...

# 2. Migrate, then wait for it.
kubectl apply -f infra/k8s/base/migration-job.yaml -n knowledge-platform-dev
kubectl wait --for=condition=complete job -l app.kubernetes.io/name=db-migrate \
  -n knowledge-platform-dev --timeout=120s

# 3. Everything else.
kubectl apply -k infra/k8s/overlays/dev
```

## Security posture: accepted trade-offs

Both surfaced by `checkov` and deliberately not "fixed" here, with the
reasoning kept next to the decision rather than just suppressed:

- **`CKV_K8S_43` (image should use digest).** Base images are tag-pinned
  (`:latest` in `base/`, overridden to `:dev`/a real tag per overlay via the
  `images:` kustomize transformer) rather than digest-pinned, because no CI
  pipeline publishes real images yet (see the repo root CI workflow). Once
  it does, switch the overlay's `images:` entries to `name@sha256:...` —
  that's a one-line change per environment once digests exist.
- **`CKV_K8S_35` (secrets as files, not env vars).** `core.config.Settings`
  is `pydantic-settings`' `BaseSettings`, which reads from the environment;
  supporting file-mounted secrets cleanly would mean a broader change to how
  every service loads config, not just the k8s manifests. Env-var secrets
  are still visible via `/proc/<pid>/environ` to anything with container
  filesystem access, same threat model a mounted file at a fixed path
  doesn't meaningfully improve on — accepted rather than a large refactor
  for a marginal gain.

Everything else `checkov` checks for k8s (non-root, high UID, dropped
capabilities, read-only root filesystem, no privilege escalation, seccomp,
readiness/liveness probes, resource requests/limits, `automountServiceAccountToken:
false`, `imagePullPolicy: Always`, NetworkPolicy coverage, no default
namespace) passes on the rendered manifests.
