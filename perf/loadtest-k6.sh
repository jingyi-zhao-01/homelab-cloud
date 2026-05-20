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

ensure_node24() {
  local required_major="${NODE_MAJOR_REQUIRED:-24}"
  local current=""

  if command -v node >/dev/null 2>&1; then
    current="$(node -v 2>/dev/null || true)"
    if [[ "$current" =~ ^v${required_major}\. ]]; then
      echo "Using Node.js ${current}"
      return 0
    fi
  fi

  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1090
    . "$NVM_DIR/nvm.sh"
    nvm install "$required_major" >/dev/null
    nvm use "$required_major" >/dev/null
    current="$(node -v 2>/dev/null || true)"
    if [[ "$current" =~ ^v${required_major}\. ]]; then
      echo "Using Node.js ${current} via nvm"
      return 0
    fi
  fi

  echo "Node.js ${required_major}.x is required by this load test wrapper."
  echo "k6 runtime itself does not need Node.js, but this project standardizes on Node ${required_major}."
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
  true
}
trap cleanup EXIT

require_cmd kubectl
require_cmd k6
require_cmd curl
ensure_node24

# Using Ingress with DNS-configured domain names
USER_HOST="homelab-user-service.jzhao62.com"
PRODUCT_HOST="homelab-product-service.jzhao62.com"
ORDER_HOST="homelab-order-service.jzhao62.com"

USER_URL="http://$USER_HOST"
PRODUCT_URL="http://$PRODUCT_HOST"
BASE_URL="http://$ORDER_HOST"

wait_http "$USER_URL" "user-service"
wait_http "$PRODUCT_URL" "product-service"
wait_http "$BASE_URL" "order-service"

k6 run \
  -e USER_URL="$USER_URL" \
  -e PRODUCT_URL="$PRODUCT_URL" \
  -e BASE_URL="$BASE_URL" \
  "$@" \
  "$LOADTEST_SCRIPT"
