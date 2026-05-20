#!/usr/bin/env bash
set -euo pipefail

if [[ -n "${KUBECONFIG_PATH:-}" ]]; then
  KUBECONFIG_PATH="$KUBECONFIG_PATH"
elif [[ -f .kube-config ]]; then
  KUBECONFIG_PATH=".kube-config"
else
  KUBECONFIG_PATH="$HOME/.kube/config"
fi

NAMESPACE="${NAMESPACE:-flashsales}"
LOADTEST_SCRIPT="${LOADTEST_SCRIPT:-./perf/loadtest.js}"

if [[ ! -r "$KUBECONFIG_PATH" ]]; then
  echo "Kubeconfig not found or not readable: $KUBECONFIG_PATH" >&2
  echo "Set KUBECONFIG_PATH explicitly or provide .kube-config / $HOME/.kube/config" >&2
  exit 1
fi

if [[ ! -r "$LOADTEST_SCRIPT" ]]; then
  echo "Loadtest script not found or not readable: $LOADTEST_SCRIPT" >&2
  exit 1
fi

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1"
    exit 1
  fi
}

pick_free_port() {
  local port
  local excluded=" $* "
  for port in $(seq 18080 18180); do
    if [[ "$excluded" == *" $port "* ]]; then
      continue
    fi
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

service_port() {
  local service_name="$1"
  local port
  port="$(KUBECONFIG="$KUBECONFIG_PATH" kubectl -n "$NAMESPACE" get svc "$service_name" -o jsonpath='{.spec.ports[0].port}')"
  if [[ -z "$port" ]]; then
    echo "Unable to resolve service port for $service_name" >&2
    exit 1
  fi
  echo "$port"
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
PRODUCT_PORT="$(pick_free_port "$USER_PORT")"
ORDER_PORT="$(pick_free_port "$USER_PORT" "$PRODUCT_PORT")"

USER_SVC_PORT="$(service_port flashsales-user-service)"
PRODUCT_SVC_PORT="$(service_port flashsales-product-service)"
ORDER_SVC_PORT="$(service_port flashsales-order-service)"

KUBECONFIG="$KUBECONFIG_PATH" kubectl -n "$NAMESPACE" port-forward svc/flashsales-user-service "$USER_PORT:$USER_SVC_PORT" >/tmp/flashsales-pf-user.log 2>&1 &
PF_USER_PID=$!

KUBECONFIG="$KUBECONFIG_PATH" kubectl -n "$NAMESPACE" port-forward svc/flashsales-product-service "$PRODUCT_PORT:$PRODUCT_SVC_PORT" >/tmp/flashsales-pf-product.log 2>&1 &
PF_PRODUCT_PID=$!

KUBECONFIG="$KUBECONFIG_PATH" kubectl -n "$NAMESPACE" port-forward svc/flashsales-order-service "$ORDER_PORT:$ORDER_SVC_PORT" >/tmp/flashsales-pf-order.log 2>&1 &
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
  "$LOADTEST_SCRIPT"
