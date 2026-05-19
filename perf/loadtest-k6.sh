#!/usr/bin/env bash
set -euo pipefail

KUBECONFIG_PATH="${KUBECONFIG_PATH:-.kube-config}"
NAMESPACE="${NAMESPACE:-flashsales}"

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

pick_free_port() {
  local port
  for port in $(seq 18080 18180); do
    if ! ss -lnt "( sport = :$port )" | grep -q ":$port"; then
      echo "$port"
      return 0
    fi
  done
  echo "No free port available in range 18080-18180" >&2
  exit 1
}

wait_http() {
  local url="$1"
  local name="$2"
  local i
  for i in $(seq 1 40); do
    if curl -fsS "$url/health" >/dev/null 2>&1 || curl -fsS "$url/docs" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for $name on $url"
  exit 1
}

cleanup() {
  [[ -n "${PF_USER_PID:-}" ]] && kill "$PF_USER_PID" >/dev/null 2>&1 || true
  [[ -n "${PF_PRODUCT_PID:-}" ]] && kill "$PF_PRODUCT_PID" >/dev/null 2>&1 || true
  [[ -n "${PF_ORDER_PID:-}" ]] && kill "$PF_ORDER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

require_cmd kubectl
require_cmd k6
require_cmd curl
require_cmd ss

USER_PORT="$(pick_free_port)"
PRODUCT_PORT="$(pick_free_port)"
while [[ "$PRODUCT_PORT" == "$USER_PORT" ]]; do
  PRODUCT_PORT="$(pick_free_port)"
done
ORDER_PORT="$(pick_free_port)"
while [[ "$ORDER_PORT" == "$USER_PORT" || "$ORDER_PORT" == "$PRODUCT_PORT" ]]; do
  ORDER_PORT="$(pick_free_port)"
done

KUBECONFIG="$KUBECONFIG_PATH" kubectl -n "$NAMESPACE" port-forward svc/flashsales-user-service "$USER_PORT:80" >/tmp/flashsales-pf-user.log 2>&1 &
PF_USER_PID=$!

KUBECONFIG="$KUBECONFIG_PATH" kubectl -n "$NAMESPACE" port-forward svc/flashsales-product-service "$PRODUCT_PORT:80" >/tmp/flashsales-pf-product.log 2>&1 &
PF_PRODUCT_PID=$!

KUBECONFIG="$KUBECONFIG_PATH" kubectl -n "$NAMESPACE" port-forward svc/flashsales-order-service "$ORDER_PORT:80" >/tmp/flashsales-pf-order.log 2>&1 &
PF_ORDER_PID=$!

USER_URL="http://127.0.0.1:$USER_PORT"
PRODUCT_URL="http://127.0.0.1:$PRODUCT_PORT"
BASE_URL="http://127.0.0.1:$ORDER_PORT"

wait_http "$USER_URL" "user-service"
wait_http "$PRODUCT_URL" "product-service"
wait_http "$BASE_URL" "order-service"

k6 run \
  -e USER_URL="$USER_URL" \
  -e PRODUCT_URL="$PRODUCT_URL" \
  -e BASE_URL="$BASE_URL" \
  "$@" \
  ./perf/loadtest.js
