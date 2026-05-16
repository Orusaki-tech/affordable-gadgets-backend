/**
 * Marketing campaign load test: 2M requests in 30 min (~1,111 req/s).
 *
 * Simulates potential customers landing on the shop, registering,
 * and browsing products. Designed to stress-test the API under
 * campaign-level traffic and collect customer data.
 *
 * Traffic mix:
 *   15%  Customer registration (POST /api/inventory/register/)
 *   10%  Customer login      (POST /api/inventory/login/)
 *   75%  Public browse       (GET  /api/v1/public/*)
 *
 * Usage:
 *   k6 run deploy/loadtest/k6-marketing.js
 *   k6 run -e TARGET_RPS=1111 -e DURATION=30m deploy/loadtest/k6-marketing.js
 */
import http from 'k6/http';
import { check } from 'k6';

// ---- Config ----
const BASE = (__ENV.BASE_URL || 'https://api-staging.affordable-gadgetske.com').replace(/\/$/, '');
const BRAND = __ENV.BRAND_CODE || 'AFFORDABLE_GADGETS';
const TARGET_RPS = Number(__ENV.TARGET_RPS || 1111);
const DURATION = __ENV.DURATION || '30m';

export const options = {
  setupTimeout: '120s',
  scenarios: {
    marketing: {
      executor: 'constant-arrival-rate',
      rate: TARGET_RPS,
      timeUnit: '1s',
      duration: DURATION,
      preAllocatedVUs: Math.max(100, Math.ceil(TARGET_RPS * 0.6)),
      maxVUs: Math.max(500, TARGET_RPS * 4),
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<5000', 'p(99)<10000'],
  },
};

// ---- Setup: fetch existing product IDs for browse mix ----
export function setup() {
  const res = http.get(`${BASE}/api/v1/public/products/?page_size=50`, {
    headers: { 'X-Brand-Code': BRAND, Accept: 'application/json' },
    tags: { name: 'setup_products' },
  });
  let ids = [];
  if (res.status === 200) {
    try {
      ids = (res.json().results || []).map((p) => p.id).filter(Boolean);
    } catch (_) {}
  }
  return { ids };
}

// ---- Helpers ----
function randStr(len) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let s = '';
  for (let i = 0; i < len; i++) s += chars[Math.floor(Math.random() * chars.length)];
  return s;
}
function randEmail() {
  return `campaign_${randStr(10)}_${Date.now()}@example.com`;
}
function randUsername() {
  return `user_${randStr(8)}_${Date.now()}`;
}
function randPhone() {
  const n = () => Math.floor(Math.random() * 10);
  return `+2547${n()}${n()}${n()}${n()}${n()}${n()}${n()}${n()}`;
}

// ---- Browse mix (same weights as smoke/2m-hour) ----
const MIX = [
  { weight: 50, tag: 'products_list',          path: () => '/api/v1/public/products/?page=1&page_size=24' },
  { weight: 20, tag: 'products_list_filtered',  path: () => '/api/v1/public/products/?page=1&page_size=12&type=PH' },
  { weight: 12, tag: 'product_detail',          path: (ids) => {
    if (!ids.length) return '/api/v1/public/products/?page=1&page_size=1';
    const id = ids[Math.floor(Math.random() * ids.length)];
    return `/api/v1/public/products/${id}/`;
  }},
  { weight: 8,  tag: 'products_brands',         path: () => '/api/v1/public/products/brands/' },
  { weight: 5,  tag: 'promotions',              path: () => '/api/v1/public/promotions/?page_size=12' },
  { weight: 3,  tag: 'bundles',                 path: () => '/api/v1/public/bundles/?page_size=12' },
  { weight: 2,  tag: 'health',                  path: () => '/health/' },
];
const cumulative = [];
let total = 0;
for (const item of MIX) {
  total += item.weight;
  cumulative.push({ ...item, threshold: total });
}
function pickEndpoint(ids) {
  const roll = Math.random() * total;
  for (const item of cumulative) {
    if (roll <= item.threshold) {
      return { tag: item.tag, url: item.path(ids) };
    }
  }
  const last = cumulative[cumulative.length - 1];
  return { tag: last.tag, url: last.path(ids) };
}

// ---- Main iteration ----
export default function (data) {
  const ids = data?.ids || [];
  const roll = Math.random();

  // 15 % — register a new customer
  if (roll < 0.15) {
    const email = randEmail();
    const payload = JSON.stringify({
      username: randUsername(),
      email: email,
      password: 'Camp@ign2026!',
      phone_number: randPhone(),
      address: `${Math.floor(Math.random() * 999) + 1} Campaign St`,
    });
    const res = http.post(`${BASE}/api/inventory/register/`, payload, {
      headers: { 'Content-Type': 'application/json', 'X-Brand-Code': BRAND, Accept: 'application/json' },
      tags: { name: 'register' },
    });
    check(res, {
      'register created': (r) => r.status === 201,
    });
    return;
  }

  // 10 % — log in (will fail email-verify, but that's expected for new customers)
  if (roll < 0.25) {
    const loginPayload = JSON.stringify({
      username_or_email: `loadtest_${randStr(6)}@example.com`,
      password: 'Camp@ign2026!',
    });
    const res = http.post(`${BASE}/api/inventory/login/`, loginPayload, {
      headers: { 'Content-Type': 'application/json', 'X-Brand-Code': BRAND, Accept: 'application/json' },
      tags: { name: 'login' },
    });
    check(res, {
      'login accepted': (r) => r.status === 200 || r.status === 400,
    });
    return;
  }

  // 75 % — browse public endpoints
  const { tag, url } = pickEndpoint(ids);
  const res = http.get(`${BASE}${url}`, {
    headers: { 'X-Brand-Code': BRAND, Accept: 'application/json' },
    tags: { name: tag },
  });
  check(res, {
    [`${tag} 2xx`]: (r) => r.status >= 200 && r.status < 300,
  });
}
