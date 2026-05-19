import http from "k6/http";
import { check, sleep } from "k6";
import exec from "k6/execution";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:18082";
const USER_URL = __ENV.USER_URL || "http://127.0.0.1:18080";
const PRODUCT_URL = __ENV.PRODUCT_URL || "http://127.0.0.1:18081";

const RAMP_UP = __ENV.RAMP_UP || "20s";
const STEADY = __ENV.STEADY || "60s";
const RAMP_DOWN = __ENV.RAMP_DOWN || "20s";
const TARGET_VUS = Number(__ENV.TARGET_VUS || 20);
const REPORT_INTERVAL_MS = Number(__ENV.REPORT_INTERVAL_MS || 5000);

let lastReportAt = Date.now();
let lastCompletedIterations = 0;

export const options = {
  stages: [
    { duration: RAMP_UP, target: TARGET_VUS },
    { duration: STEADY, target: TARGET_VUS },
    { duration: RAMP_DOWN, target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1500"],
  },
};

function postJson(url, body) {
  return http.post(url, JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    timeout: "10s",
  });
}

export function setup() {
  const ts = Date.now();

  const userRes = postJson(`${USER_URL}/users`, {
    email: `k6-${ts}@example.com`,
    name: "k6 user",
  });

  check(userRes, {
    "setup user created": (r) => r.status === 200 || r.status === 201,
  });

  const user = userRes.json();

  const productRes = postJson(`${PRODUCT_URL}/products`, {
    name: `k6-product-${ts}`,
    price: 9.99,
    stock: 100000,
  });

  check(productRes, {
    "setup product created": (r) => r.status === 200 || r.status === 201,
  });

  const product = productRes.json();

  return {
    user_id: user.id,
    product_id: product.id,
  };
}

export default function loadtestScenario(data) {
  const orderRes = postJson(`${BASE_URL}/orders`, {
    user_id: data.user_id,
    product_id: data.product_id,
    quantity: 1,
  });

  check(orderRes, {
    "order accepted": (r) => r.status === 200 || r.status === 201,
  });

  // Print runtime markers in CI logs (manual GitHub Actions runs).
  if (__VU === 1) {
    const now = Date.now();
    if (now - lastReportAt >= REPORT_INTERVAL_MS) {
      const completedIterations = exec.instance.iterationsCompleted;
      const elapsedSec = (now - lastReportAt) / 1000;
      const tps = elapsedSec > 0 ? (completedIterations - lastCompletedIterations) / elapsedSec : 0;
      const activeVus = exec.instance.vusActive;
      console.log(`[k6-runtime] active_vu=${activeVus} approx_tps=${tps.toFixed(2)}`);
      lastReportAt = now;
      lastCompletedIterations = completedIterations;
    }
  }

  sleep(1);
}
