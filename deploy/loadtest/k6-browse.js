/**
 * Legacy stage-based browse test (~9 min, peaks ~200 VUs).
 * For 2M requests/hour use k6-2m-hour.js or: ./deploy/loadtest/run.sh 2m-hour
 *
 * Run: k6 run -e BASE_URL=https://api-staging.affordable-gadgetske.com deploy/loadtest/k6-browse.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 50 },
    { duration: '5m', target: 200 },
    { duration: '2m', target: 0 },
  ],
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<3000'],
  },
};

const API = __ENV.BASE_URL || 'https://api.affordable-gadgetske.com';
const BRAND = __ENV.BRAND_CODE || 'AFFORDABLE_GADGETS';

export default function () {
  const headers = { 'X-Brand-Code': BRAND };
  const health = http.get(`${API}/health/`);
  check(health, { 'health 200': (r) => r.status === 200 });

  const products = http.get(`${API}/api/v1/public/products/?page=1&page_size=24`, { headers });
  check(products, { 'products 200': (r) => r.status === 200 });

  sleep(1);
}
