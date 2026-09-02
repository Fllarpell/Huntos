import http from "k6/http";
import { check, sleep } from "k6";

// Laptop compose: BASE_URL=https://127.0.0.1:8443 k6 run --insecure-skip-tls-verify infra/k6/smoke.js
// Local uvicorn:  k6 run infra/k6/smoke.js

export const options = {
  vus: 2,
  duration: "20s",
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<2000"],
  },
};

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8000";

export default function () {
  const live = http.get(`${BASE}/api/health`);
  check(live, { "health 200": (r) => r.status === 200 });
  const ready = http.get(`${BASE}/api/ready`);
  check(ready, { "ready 200": (r) => r.status === 200 });
  if (BASE.includes("8443") || BASE.includes("https://")) {
    const metrics = http.get(`${BASE}/api/metrics`);
    check(metrics, { "metrics hidden on edge": (r) => r.status === 404 });
  }
  sleep(1.2);
}
