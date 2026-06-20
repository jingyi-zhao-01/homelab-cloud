# Self-Hosted Datadog

This directory tracks the non-secret deploy inputs for running the Datadog
operator plus a `DatadogAgent` custom resource inside the k3s cluster.

## Layout

- `operator-values.yaml`
  Helm values passed to `datadog/datadog-operator`.
- `manifests/`
  Kustomize entrypoint for the Datadog runtime resources that should exist after
  the operator is installed.

## Secret source

The Datadog API key is expected to already exist in AWS Systems Manager
Parameter Store at:

- `/datadog/api_key`

The runtime secret is materialized by External Secrets into the `datadog`
namespace as:

- `Secret/datadog-secret`

## Manual deploy

```bash
helm repo add datadog https://helm.datadoghq.com
helm repo update

kubectl create namespace datadog --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install datadog-operator datadog/datadog-operator \
  --namespace datadog \
  --create-namespace \
  -f deploy/monitoring/self-hosted/datadog/operator-values.yaml

kubectl apply -k deploy/monitoring/self-hosted/datadog/manifests
```

## Manual remove

```bash
kubectl delete -k deploy/monitoring/self-hosted/datadog/manifests --ignore-not-found
helm uninstall datadog-operator -n datadog || true
```
