#!/usr/bin/env bash
set -euo pipefail

if [ -z "${NAMESPACE:-}" ]; then
  echo "NAMESPACE is required" >&2
  exit 1
fi

if [ -z "${GHCR_PULL_USERNAME:-}" ] || [ -z "${GHCR_PULL_TOKEN:-}" ]; then
  echo "GHCR_PULL_USERNAME and GHCR_PULL_TOKEN are required" >&2
  exit 1
fi

if [ -z "${AWS_ACCESS_KEY_ID:-}" ] || [ -z "${AWS_SECRET_ACCESS_KEY:-}" ]; then
  echo "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required" >&2
  exit 1
fi

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NAMESPACE" create secret docker-registry ghcr-pull-secret \
  --docker-server=ghcr.io \
  --docker-username="$GHCR_PULL_USERNAME" \
  --docker-password="$GHCR_PULL_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create namespace external-secrets --dry-run=client -o yaml | kubectl apply -f -

kubectl -n external-secrets create secret generic aws-ssm-credentials \
  --from-literal=access-key-id="$AWS_ACCESS_KEY_ID" \
  --from-literal=secret-access-key="$AWS_SECRET_ACCESS_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
