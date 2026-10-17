// Beat 13.1. Find the concurrency where the service breaks, not the model.
//
// Run against FAKE_MODEL=true. The gateway is the only part that costs
// money, and it is also the part that would dominate every latency number
// and tell you nothing about your own code. What is under test here is
// Granian, the Session per request, the Redis round trip and Postgres.
//
//   k6 run ops/k6/chat_load.js
//
// The rate limiter must be raised for the run or every virtual user gets a
// 429 after ten requests and the test measures the limiter instead.

import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const rateLimited = new Counter('rate_limited');

// Ramp by default, to see the shape. With VUS set, hold one level steady,
// which is how you find the concurrency where the budget breaks rather
// than an average across every level you passed through.
const VUS = Number(__ENV.VUS || 0);

const thresholds = {
  http_req_duration: ['p(95)<500'],
  http_req_failed: ['rate<0.01'],
};

export const options = VUS
  ? { vus: VUS, duration: __ENV.DURATION || '30s', thresholds }
  : {
      stages: [
        { duration: '30s', target: 5 },
        { duration: '30s', target: 10 },
        { duration: '30s', target: 20 },
        { duration: '30s', target: 40 },
        { duration: '15s', target: 0 },
      ],
      thresholds,
    };

const URL = __ENV.TARGET || 'http://127.0.0.1:8000/chat';
const KEY = __ENV.API_KEY || 'dev-key-owner';

export default function () {
  const response = http.post(
    URL,
    JSON.stringify({ message: 'My order ord_C1_01 arrived damaged.' }),
    { headers: { 'Content-Type': 'application/json', 'X-API-Key': KEY } },
  );

  // A 429 is the limiter working, not the service failing. Counted apart
  // so it cannot quietly pass as an error rate.
  if (response.status === 429) {
    rateLimited.add(1);
  }

  check(response, {
    'status is 200': (r) => r.status === 200,
    'body has a decision': (r) => r.body.includes('decision'),
  });
}
