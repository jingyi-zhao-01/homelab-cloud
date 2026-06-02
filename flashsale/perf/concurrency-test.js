import http from "k6/http";
import { check } from "k6";
import exec from "k6/execution";
import { Counter, Rate } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://homelab-order-service.jzhao62.com";
const USER_URL = __ENV.USER_URL || "http://homelab-user-service.jzhao62.com";
const PRODUCT_URL = __ENV.PRODUCT_URL || "http://homelab-product-service.jzhao62.com";
const K6_HTTP_TIMEOUT = __ENV.K6_HTTP_TIMEOUT || "20s";
const PROFILE = __ENV.PROFILE || "smoke";
const REPORT_INTERVAL_MS = Number(__ENV.REPORT_INTERVAL_MS || 5000);

const PROFILE_DEFAULTS = {
  smoke: {
    tps: 10,
    duration: "3m",
    p50: 100,
    p90: 200,
    p99: 500,
    max5xxRate: 0,
    productCount: 1,
    userCount: 200,
    initialStock: 3000,
  },
  baseline: {
    tps: 50,
    duration: "8m",
    p50: 100,
    p90: 300,
    p99: 800,
    max5xxRate: 0.01,
    productCount: 20,
    userCount: 1000,
    initialStock: 2000,
  },
  stress100: {
    tps: 100,
    duration: "5m",
    p50: 150,
    p90: 500,
    p99: 1200,
    max5xxRate: 0.02,
    productCount: 30,
    userCount: 2000,
    initialStock: 1500,
  },
  stress200: {
    tps: 200,
    duration: "3m",
    p50: 150,
    p90: 500,
    p99: 2000,
    max5xxRate: 0.02,
    productCount: 40,
    userCount: 3000,
    initialStock: 1200,
  },
  hotspot: {
    tps: 100,
    duration: "3m",
    p50: 150,
    p90: 500,
    p99: 2000,
    max5xxRate: 0.01,
    productCount: 1,
    userCount: 1000,
    initialStock: 1,
  },
};

const selectedProfile = PROFILE_DEFAULTS[PROFILE] || PROFILE_DEFAULTS.smoke;
const TARGET_TPS = Number(__ENV.TARGET_TPS || selectedProfile.tps);
const TEST_DURATION = __ENV.TEST_DURATION || selectedProfile.duration;
const P50_MS = Number(__ENV.K6_P50_THRESHOLD_MS || selectedProfile.p50);
const P90_MS = Number(__ENV.K6_P90_THRESHOLD_MS || selectedProfile.p90);
const P99_MS = Number(__ENV.K6_P99_THRESHOLD_MS || selectedProfile.p99);
const MAX_5XX_RATE = Number(__ENV.MAX_5XX_RATE || selectedProfile.max5xxRate);
const PRODUCT_COUNT = Number(__ENV.PRODUCT_COUNT || selectedProfile.productCount);
const USER_COUNT = Number(__ENV.USER_COUNT || selectedProfile.userCount);
const INITIAL_STOCK = Number(__ENV.INITIAL_STOCK || selectedProfile.initialStock);
const PRE_ALLOCATED_VUS = Number(
  __ENV.PRE_ALLOCATED_VUS || Math.max(20, TARGET_TPS * 2),
);
const MAX_VUS = Number(__ENV.MAX_VUS || Math.max(200, TARGET_TPS * 10));

const TEST_DESCRIPTION =
  __ENV.TEST_DESCRIPTION ||
  `Concurrency profile=${PROFILE} tps=${TARGET_TPS} duration=${TEST_DURATION}`;
const POST_CLEANUP = (__ENV.POST_CLEANUP || "true").toLowerCase() === "true";

const http5xxRate = new Rate("http_5xx_rate");
const oversellViolations = new Counter("oversell_violations");
const orderSuccessTotal = new Counter("order_success_total");
const businessRejectTotal = new Counter("business_reject_total");

let lastReportAt = Date.now();
let lastCompletedIterations = 0;

http.setResponseCallback(http.expectedStatuses({ min: 200, max: 204 }, 409, 404));

export const options = {
  scenarios: {
    concurrency_test: {
      executor: "constant-arrival-rate",
      rate: TARGET_TPS,
      timeUnit: "1s",
      duration: TEST_DURATION,
      preAllocatedVUs: PRE_ALLOCATED_VUS,
      maxVUs: MAX_VUS,
    },
  },
  thresholds: {
    http_req_duration: [
      `p(50)<${P50_MS}`,
      `p(90)<${P90_MS}`,
      `p(99)<${P99_MS}`,
    ],
    http_5xx_rate: [`rate<=${MAX_5XX_RATE}`],
    oversell_violations: ["count==0"],
  },
};

function postJson(url, body) {
  return http.post(url, JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
    timeout: K6_HTTP_TIMEOUT,
  });
}

function failIfNotStatus(res, expectedStatus, message) {
  check(res, {
    [message]: (r) => r.status === expectedStatus,
  });
}

function resetServiceDb(url, serviceName) {
  const res = http.post(`${url}/admin/reset`, null, {
    timeout: K6_HTTP_TIMEOUT,
  });
  const ok = res.status === 204;
  check(res, {
    [`post-cleanup ${serviceName} database reset`]: (r) => r.status === 204,
  });
  if (!ok) {
    console.log(
      `[k6-post-cleanup] reset_failed service=${serviceName} status=${res.status}`,
    );
  }
  return ok;
}

function runPostCleanup() {
  if (!POST_CLEANUP) {
    console.log("[k6-post-cleanup] skipped (POST_CLEANUP=false)");
    return;
  }

  const orderOk = resetServiceDb(BASE_URL, "order");
  const userOk = resetServiceDb(USER_URL, "user");
  const productOk = resetServiceDb(PRODUCT_URL, "product");
  const allOk = orderOk && userOk && productOk;
  console.log(
    `[k6-post-cleanup] completed order_reset=${orderOk} user_reset=${userOk} product_reset=${productOk} all_ok=${allOk}`,
  );
}

export function setup() {
  console.log(`[k6-scenario] ${TEST_DESCRIPTION}`);

  const resetOrderRes = http.post(`${BASE_URL}/admin/reset`, null, {
    timeout: K6_HTTP_TIMEOUT,
  });
  failIfNotStatus(resetOrderRes, 204, "order database reset");

  const resetUserRes = http.post(`${USER_URL}/admin/reset`, null, {
    timeout: K6_HTTP_TIMEOUT,
  });
  failIfNotStatus(resetUserRes, 204, "user database reset");

  const resetProductRes = http.post(`${PRODUCT_URL}/admin/reset`, null, {
    timeout: K6_HTTP_TIMEOUT,
  });
  failIfNotStatus(resetProductRes, 204, "product database reset");

  const users = [];
  for (let i = 0; i < USER_COUNT; i += 1) {
    const userRes = postJson(`${USER_URL}/users`, {
      email: `k6-${PROFILE}-u${i}-${Date.now()}@example.com`,
      name: `k6 user ${i}`,
    });
    check(userRes, {
      "setup user created": (r) => r.status === 200 || r.status === 201,
    });
    users.push(userRes.json().id);
  }

  const products = [];
  for (let i = 0; i < PRODUCT_COUNT; i += 1) {
    const productRes = postJson(`${PRODUCT_URL}/products`, {
      name: `k6-${PROFILE}-p${i}-${Date.now()}`,
      price: 9.99,
      stock: INITIAL_STOCK,
    });
    check(productRes, {
      "setup product created": (r) => r.status === 200 || r.status === 201,
    });
    products.push(productRes.json().id);
  }

  return {
    users,
    products,
    initialStock: INITIAL_STOCK,
  };
}

export default function concurrencyTest(data) {
  const userId = data.users[exec.scenario.iterationInTest % data.users.length];
  const productId =
    PROFILE === "hotspot"
      ? data.products[0]
      : data.products[exec.scenario.iterationInTest % data.products.length];

  const orderRes = postJson(`${BASE_URL}/orders`, {
    user_id: userId,
    items: [{ product_id: productId, quantity: 1 }],
  });

  const is5xx = orderRes.status >= 500;
  http5xxRate.add(is5xx);

  if (orderRes.status === 200 || orderRes.status === 201) {
    orderSuccessTotal.add(1);
  } else if (orderRes.status === 409 || orderRes.status === 404) {
    businessRejectTotal.add(1);
  }

  if (__VU === 1) {
    const now = Date.now();
    if (now - lastReportAt >= REPORT_INTERVAL_MS) {
      const completedIterations = exec.instance.iterationsCompleted;
      const elapsedSec = (now - lastReportAt) / 1000;
      const tps =
        elapsedSec > 0
          ? (completedIterations - lastCompletedIterations) / elapsedSec
          : 0;
      console.log(`[k6-runtime] profile=${PROFILE} approx_tps=${tps.toFixed(2)}`);
      lastReportAt = now;
      lastCompletedIterations = completedIterations;
    }
  }
}

export function teardown(data) {
  const listOrdersRes = http.get(`${BASE_URL}/orders`, {
    timeout: K6_HTTP_TIMEOUT,
  });
  let violations = 0;

  if (listOrdersRes.status !== 200) {
    oversellViolations.add(1);
    violations += 1;
    console.log("[k6-correctness] unable to list orders for oversell check");
  } else {
    const orders = listOrdersRes.json();
    const soldByProduct = {};
    for (const order of orders) {
      for (const item of order.items || []) {
        const productId = Number(item.product_id);
        const quantity = Number(item.quantity || 0);
        soldByProduct[productId] = (soldByProduct[productId] || 0) + quantity;
      }
    }

    for (const productId of data.products) {
      const sold = soldByProduct[Number(productId)] || 0;
      if (sold > data.initialStock) {
        violations += 1;
        console.log(
          `[k6-correctness] oversell_detected product_id=${productId} sold=${sold} initial_stock=${data.initialStock}`,
        );
      }
    }
  }

  if (violations > 0) {
    oversellViolations.add(violations);
  }

  runPostCleanup();
}
