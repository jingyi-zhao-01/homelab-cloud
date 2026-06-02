#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$REPO_ROOT/flashsale/docker-compose.yaml}"
BASE_USER_URL="${BASE_USER_URL:-http://127.0.0.1:18001}"
BASE_PRODUCT_URL="${BASE_PRODUCT_URL:-http://127.0.0.1:18002}"
BASE_ORDER_URL="${BASE_ORDER_URL:-http://127.0.0.1:18003}"
RUN_ID="${RUN_ID:-$(date +%s)}"

log() {
  echo "[flashsale-compose] $*"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

wait_for_http() {
  local url="$1"
  for _ in $(seq 1 60); do
    if curl --max-time 1 -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "Timeout waiting for $url" >&2
  exit 1
}

json_get() {
  local json_payload="$1"
  local field_name="$2"
  python3 - "$json_payload" "$field_name" <<'PY'
import json
import sys

payload, field = sys.argv[1], sys.argv[2]
obj = json.loads(payload)
value = obj[field]
if isinstance(value, bool):
    print("true" if value else "false")
else:
    print(value)
PY
}

json_post() {
  local url="$1"
  local payload="$2"
  curl -fsS -X POST "$url" -H 'Content-Type: application/json' -d "$payload"
}

reset_services() {
  curl -fsS -X POST "$BASE_USER_URL/admin/reset" >/dev/null
  curl -fsS -X POST "$BASE_PRODUCT_URL/admin/reset" >/dev/null
  curl -fsS -X POST "$BASE_ORDER_URL/admin/reset" >/dev/null
}

require_cmd docker
require_cmd curl
require_cmd python3

cleanup() {
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

log "Starting flashsale integration stack"
docker compose -f "$COMPOSE_FILE" up -d --build

wait_for_http "$BASE_USER_URL/health"
wait_for_http "$BASE_PRODUCT_URL/health"
wait_for_http "$BASE_ORDER_URL/health"

reset_services

log "Scenario: create user and product"
USER_EMAIL="compose.user.${RUN_ID}@example.com"
USER_RESP=$(json_post "$BASE_USER_URL/users" "{\"name\":\"Compose User\",\"email\":\"${USER_EMAIL}\"}")
USER_ID=$(json_get "$USER_RESP" "id")

PRODUCT_RESP=$(json_post "$BASE_PRODUCT_URL/products" '{"name":"Compose Product","price":19.99,"stock":5}')
PRODUCT_ID=$(json_get "$PRODUCT_RESP" "id")

log "Scenario: product reserve / confirm through order creation"
ORDER_RESP=$(json_post "$BASE_ORDER_URL/orders" "{\"user_id\":${USER_ID},\"idempotency_key\":\"compose-order-1\",\"items\":[{\"product_id\":${PRODUCT_ID},\"quantity\":2}]}")
ORDER_ID=$(json_get "$ORDER_RESP" "id")
ORDER_STATUS=$(json_get "$ORDER_RESP" "status")
PAYMENT_STATUS=$(json_get "$ORDER_RESP" "payment_status")
if [[ "$ORDER_STATUS" != "confirmed" || "$PAYMENT_STATUS" != "succeeded" ]]; then
  echo "Unexpected order status after creation: status=$ORDER_STATUS payment=$PAYMENT_STATUS" >&2
  exit 1
fi

PRODUCT_AFTER_ORDER=$(curl -fsS "$BASE_PRODUCT_URL/products/${PRODUCT_ID}")
STOCK_AFTER_ORDER=$(json_get "$PRODUCT_AFTER_ORDER" "stock")
if [[ "$STOCK_AFTER_ORDER" != "3" ]]; then
  echo "Unexpected stock after order: $STOCK_AFTER_ORDER" >&2
  exit 1
fi

log "Scenario: duplicate order replay"
DUPLICATE_RESP=$(json_post "$BASE_ORDER_URL/orders" "{\"user_id\":${USER_ID},\"idempotency_key\":\"compose-order-1\",\"items\":[{\"product_id\":${PRODUCT_ID},\"quantity\":2}]}")
DUPLICATE_ID=$(json_get "$DUPLICATE_RESP" "id")
if [[ "$DUPLICATE_ID" != "$ORDER_ID" ]]; then
  echo "Duplicate order created a new id: $DUPLICATE_ID expected $ORDER_ID" >&2
  exit 1
fi

PRODUCT_AFTER_DUP=$(curl -fsS "$BASE_PRODUCT_URL/products/${PRODUCT_ID}")
STOCK_AFTER_DUP=$(json_get "$PRODUCT_AFTER_DUP" "stock")
if [[ "$STOCK_AFTER_DUP" != "3" ]]; then
  echo "Duplicate order changed stock: $STOCK_AFTER_DUP" >&2
  exit 1
fi

log "Scenario: out of stock returns 409"
HTTP_CODE=$(curl -sS -o /tmp/flashsale-out-of-stock.json -w "%{http_code}" -X POST "$BASE_ORDER_URL/orders" \
  -H 'Content-Type: application/json' \
  -d "{\"user_id\":${USER_ID},\"idempotency_key\":\"compose-order-oos\",\"items\":[{\"product_id\":${PRODUCT_ID},\"quantity\":4}]}")
if [[ "$HTTP_CODE" != "409" ]]; then
  echo "Expected 409 for out of stock, got $HTTP_CODE" >&2
  cat /tmp/flashsale-out-of-stock.json >&2
  exit 1
fi

log "Scenario: duplicate payment webhook is idempotent"
WEBHOOK_RESP=$(json_post "$BASE_ORDER_URL/payments/webhook" "{\"order_id\":${ORDER_ID},\"event_id\":\"evt-compose-1\",\"status\":\"succeeded\"}")
WEBHOOK_STATUS=$(json_get "$WEBHOOK_RESP" "status")
WEBHOOK_PAYMENT=$(json_get "$WEBHOOK_RESP" "payment_status")
if [[ "$WEBHOOK_STATUS" != "confirmed" || "$WEBHOOK_PAYMENT" != "succeeded" ]]; then
  echo "Unexpected webhook replay state: status=$WEBHOOK_STATUS payment=$WEBHOOK_PAYMENT" >&2
  exit 1
fi

log "Scenario: timeout cleanup beats late payment"
PRODUCT_2_RESP=$(json_post "$BASE_PRODUCT_URL/products" '{"name":"Pending Product","price":29.99,"stock":5}')
PRODUCT_2_ID=$(json_get "$PRODUCT_2_RESP" "id")
HTTP_CODE=$(curl -sS -o /tmp/flashsale-pending-order.json -w "%{http_code}" -X POST "$BASE_PRODUCT_URL/products/${PRODUCT_2_ID}/reserve" \
  -H 'Content-Type: application/json' \
  -d '{"quantity":1}')
if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Expected direct reservation to succeed for pending order setup, got $HTTP_CODE" >&2
  cat /tmp/flashsale-pending-order.json >&2
  exit 1
fi
RESERVE_RESP=$(cat /tmp/flashsale-pending-order.json)
RESERVATION_ID=$(json_get "$RESERVE_RESP" "reservation_id")
PENDING_ORDER_RESP=$(SEED_USER_ID="$USER_ID" \
SEED_PRODUCT_ID="$PRODUCT_2_ID" \
SEED_RESERVATION_ID="$RESERVATION_ID" \
docker compose -f "$COMPOSE_FILE" exec -T -e SEED_USER_ID -e SEED_PRODUCT_ID -e SEED_RESERVATION_ID order-service python -c '
import json
import os
import psycopg

database_url = os.environ["DATABASE_URL"]
user_id = int(os.environ["SEED_USER_ID"])
product_id = int(os.environ["SEED_PRODUCT_ID"])
reservation_id = int(os.environ["SEED_RESERVATION_ID"])

with psycopg.connect(database_url, autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO orders (
                user_id,
                total_amount,
                status,
                payment_status,
                idempotency_key,
                reservation_ids_json,
                items_json,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, NOW() - interval '"'"'5 minutes'"'"')
            RETURNING id
            """,
            (
                user_id,
                29.99,
                "pending",
                "pending",
                "compose-pending-order",
                json.dumps([reservation_id]),
                json.dumps([{
                    "product_id": product_id,
                    "quantity": 1,
                    "unit_price": 29.99,
                    "line_total": 29.99,
                }]),
            ),
        )
        row = cur.fetchone()
        print(json.dumps({"id": row[0]}))
' | tr -d '\r')
PENDING_ORDER_ID=$(json_get "$PENDING_ORDER_RESP" "id")
EXPIRE_RESP=$(curl -fsS -X POST "$BASE_ORDER_URL/admin/expire-orders")
EXPIRED_COUNT=$(json_get "$EXPIRE_RESP" "expired_count")
if [[ "$EXPIRED_COUNT" != "1" ]]; then
  echo "Expected one expired pending order, got $EXPIRED_COUNT" >&2
  exit 1
fi
LATE_WEBHOOK_RESP=$(json_post "$BASE_ORDER_URL/payments/webhook" "{\"order_id\":${PENDING_ORDER_ID},\"event_id\":\"evt-compose-late\",\"status\":\"succeeded\"}")
LATE_STATUS=$(json_get "$LATE_WEBHOOK_RESP" "status")
LATE_PAYMENT=$(json_get "$LATE_WEBHOOK_RESP" "payment_status")
if [[ "$LATE_STATUS" != "expired" || "$LATE_PAYMENT" != "cancelled" ]]; then
  echo "Late payment webhook resurrected expired order: status=$LATE_STATUS payment=$LATE_PAYMENT" >&2
  exit 1
fi

log "Integration PASS"
