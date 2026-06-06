# Monitoring Deploy Inputs

This directory holds tracked monitoring deployment inputs that are safe and useful
to keep in the repository.

## Layout

- `self-hosted/`
  Tracked Helm values for monitoring components that run inside the cluster and
  are intended to be deployed from this repository.

- `cloud-managed/`
  Reserved for tracked templates or manifests that configure hosted monitoring
  integrations without embedding live credentials.

## What stays out of this directory

Cluster-private or credential-bearing operator values should remain outside this
tracked directory. In this repo, those stay in `secrets/` or are supplied by
GitHub secrets / variables at workflow runtime.

Examples:

- `secrets/grafana-k8s-monitoring-values.yaml`
- OTLP auth headers
- webhook URLs
- kubeconfig material

## Current entrypoints

- self-hosted Prometheus values:
  `deploy/monitoring/self-hosted/prometheus-values.yaml.tmpl`

- GitHub Actions manual deploy workflow:
  `.github/workflows/deploy-selfhosted-prometheus.yml`
