/**
 * Shared k6 helpers — public API traffic mix (read-only GET).
 */
import http from 'k6/http';
import { check } from 'k6';

export function config() {
  const targetRps = Number(__ENV.TARGET_RPS || 556);
  const duration = __ENV.DURATION || '1h';
  return {
    api: (__ENV.BASE_URL || 'https://api-staging.affordable-gadgetske.com').replace(/\/$/, ''),
    brand: __ENV.BRAND_CODE || 'AFFORDABLE_GADGETS',
    targetRps,
    duration,
    preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || Math.max(100, Math.ceil(targetRps * 0.6))),
    maxVUs: Number(__ENV.MAX_VUS || Math.max(500, targetRps * 4)),
  };
}

export function brandHeaders(brand) {
  return {
    'X-Brand-Code': brand,
    Accept: 'application/json',
  };
}

/** Fetch product IDs once for detail traffic. */
export function setupProductIds() {
  const { api, brand } = config();
  const res = http.get(`${api}/api/v1/public/products/?page_size=50`, {
    headers: brandHeaders(brand),
    tags: { name: 'setup_products' },
  });
  if (res.status !== 200) {
    console.warn(`setup products list failed: ${res.status}`);
    return { ids: [] };
  }
  let body;
  try {
    body = res.json();
  } catch {
    return { ids: [] };
  }
  const ids = (body.results || []).map((p) => p.id).filter(Boolean);
  return { ids };
}

const MIX = [
  { weight: 50, tag: 'products_list', path: () => '/api/v1/public/products/?page=1&page_size=24' },
  { weight: 20, tag: 'products_list_filtered', path: () => '/api/v1/public/products/?page=1&page_size=12&type=PH' },
  { weight: 12, tag: 'product_detail', path: (ids) => {
    if (!ids.length) return '/api/v1/public/products/?page=1&page_size=1';
    const id = ids[Math.floor(Math.random() * ids.length)];
    return `/api/v1/public/products/${id}/`;
  }},
  { weight: 8, tag: 'products_brands', path: () => '/api/v1/public/products/brands/' },
  { weight: 5, tag: 'promotions', path: () => '/api/v1/public/promotions/?page_size=12' },
  { weight: 3, tag: 'bundles', path: () => '/api/v1/public/bundles/?page_size=12' },
  { weight: 2, tag: 'health', path: () => '/health/' },
];

const cumulative = [];
let total = 0;
for (const item of MIX) {
  total += item.weight;
  cumulative.push({ ...item, threshold: total });
}

function pickEndpoint(productIds) {
  const roll = Math.random() * total;
  for (const item of cumulative) {
    if (roll <= item.threshold) {
      return { tag: item.tag, url: item.path(productIds) };
    }
  }
  const last = cumulative[cumulative.length - 1];
  return { tag: last.tag, url: last.path(productIds) };
}

/**
 * One HTTP GET drawn from the browse mix. Use with constant-arrival-rate so
 * each iteration ≈ one request toward your TARGET_RPS budget.
 */
export function trafficRequest(productIds = []) {
  const { api, brand } = config();
  const { tag, url } = pickEndpoint(productIds);
  const res = http.get(`${api}${url}`, {
    headers: brandHeaders(brand),
    tags: { name: tag },
  });
  check(res, {
    [`${tag} status 2xx`]: (r) => r.status >= 200 && r.status < 300,
  });
  return res;
}

export function constantRateScenario(overrides = {}) {
  const cfg = config();
  return {
    executor: 'constant-arrival-rate',
    rate: cfg.targetRps,
    timeUnit: '1s',
    duration: cfg.duration,
    preAllocatedVUs: cfg.preAllocatedVUs,
    maxVUs: cfg.maxVUs,
    ...overrides,
  };
}

export const defaultThresholds = {
  http_req_failed: ['rate<0.01'],
  http_req_duration: ['p(95)<3000', 'p(99)<8000'],
};
