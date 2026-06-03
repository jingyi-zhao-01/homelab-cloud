import http from "k6/http";
import { sleep } from "k6";
import { Rate } from "k6/metrics";

// This scenario replays the same order payload twice and asserts dedupe at both
// the order identity layer and the inventory-consumption layer.

import {
  buildRampOptions,
  createPostJson,
  createRuntimeReporter,
  envNumber,
  envString,
  checkStatus,
  resetService,
  seedProducts,
  createUser,
  createProduct,
} from "../lib/k6-common.js";

const BASE_URL = envString("BASE_URL", "http://127.0.0.1:18082");
const USER_URL = envString("USER_URL", "http://127.0.0.1:18080");
const PRODUCT_URL = envString("PRODUCT_URL", "http://127.0.0.1:18081");

const RAMP_UP = envString("RAMP_UP", "10s");
const STEADY = envString("STEADY", "20s");
const RAMP_DOWN = envString("RAMP_DOWN", "10s");
const TARGET_VUS = envNumber("TARGET_VUS", 5);
const REPORT_INTERVAL_MS = envNumber("REPORT_INTERVAL_MS", 5000);
const K6_HTTP_TIMEOUT = envString("K6_HTTP_TIMEOUT", "20s");
const STOCK_PER_PRODUCT = envNumber("STOCK_PER_PRODUCT", 5);
const K6_P50_THRESHOLD_MS = envNumber("K6_P50_THRESHOLD_MS", 1000);
const K6_P90_THRESHOLD_MS = envNumber("K6_P90_THRESHOLD_MS", 1500);
const K6_P95_THRESHOLD_MS = envNumber("K6_P95_THRESHOLD_MS", 2000);
const TEST_DESCRIPTION = envString(
  "TEST_DESCRIPTION",
  "Idempotency lite: replay the same order request and verify one order plus one stock decrement",
);

const idempotencyMismatchRate = new Rate("idempotency_mismatch_rate");
const stockDoubleConsumeRate = new Rate("idempotency_stock_double_consume_rate");

const postJson = createPostJson(K6_HTTP_TIMEOUT);
const reportRuntime = createRuntimeReporter(
  REPORT_INTERVAL_MS,
  ({ activeVus, tps }) =>
    `[k6-runtime] active_vu=${activeVus} approx_tps=${tps.toFixed(2)}`,
);

export const options = buildRampOptions({
  rampUp: RAMP_UP,
  steady: STEADY,
  rampDown: RAMP_DOWN,
  targetVus: TARGET_VUS,
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: [
      `p(50)<${K6_P50_THRESHOLD_MS}`,
      `p(90)<${K6_P90_THRESHOLD_MS}`,
      `p(95)<${K6_P95_THRESHOLD_MS}`,
    ],
    idempotency_mismatch_rate: ["rate==0"],
    idempotency_stock_double_consume_rate: ["rate==0"],
  },
});

export function setup() {
  console.log(`[k6-scenario] ${TEST_DESCRIPTION}`);

  const ts = Date.now();

  // Keep one stable user for the run; each iteration creates its own product.
  resetService(BASE_URL, "order", K6_HTTP_TIMEOUT);
  resetService(USER_URL, "user", K6_HTTP_TIMEOUT);
  seedProducts(PRODUCT_URL, K6_HTTP_TIMEOUT);

  const user = createUser({
    userUrl: USER_URL,
    email: `k6-idempotency-${ts}@example.com`,
    name: "k6 idempotency user",
    postJson,
  });

  return {
    user_id: user.id,
  };
}

export default function loadtestScenario(data) {
  const iteration = exec.scenario.iterationInTest;
  const productKey = `k6-idempotency-product-${__VU}-${iteration}`;
  const idempotencyKey = `k6-idempotency-order-${__VU}-${iteration}`;

  // A fresh product per iteration makes stock assertions deterministic.
  const product = createProduct({
    productUrl: PRODUCT_URL,
    name: productKey,
    price: 9.99,
    stock: STOCK_PER_PRODUCT,
    postJson,
    label: "iteration product created",
  });

  const payload = {
    user_id: data.user_id,
    idempotency_key: idempotencyKey,
    items: [
      {
        product_id: product.id,
        quantity: 1,
      },
    ],
  };

  const firstOrderRes = postJson(`${BASE_URL}/orders`, payload);
  const replayOrderRes = postJson(`${BASE_URL}/orders`, payload);

  const firstAccepted = firstOrderRes.status === 200 || firstOrderRes.status === 201;
  const replayAccepted = replayOrderRes.status === 200 || replayOrderRes.status === 201;

  checkStatus(firstOrderRes, "first order accepted", [200, 201]);
  checkStatus(replayOrderRes, "replay order accepted", [200, 201]);

  let sameOrder = false;
  if (firstAccepted && replayAccepted) {
    const firstOrder = firstOrderRes.json();
    const replayOrder = replayOrderRes.json();
    sameOrder = String(firstOrder.id) === String(replayOrder.id);
  }
  idempotencyMismatchRate.add(!(firstAccepted && replayAccepted && sameOrder));

  const productAfterRes = http.get(`${PRODUCT_URL}/products/${product.id}`, {
    timeout: K6_HTTP_TIMEOUT,
  });
  checkStatus(productAfterRes, "product fetch after replay", 200);

  let singleDecrement = false;
  if (productAfterRes.status === 200) {
    const productAfter = productAfterRes.json();
    singleDecrement = Number(productAfter.stock) === STOCK_PER_PRODUCT - 1;
  }
  stockDoubleConsumeRate.add(!singleDecrement);

  reportRuntime();

  sleep(1);
}
