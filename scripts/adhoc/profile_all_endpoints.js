/**
 * Hits all GET endpoints (admin + public) so you can profile query counts in Django Silk.
 * Uses admin / 6foot7foot for authenticated endpoints; public endpoints called without auth.
 *
 * Run: node profile_all_endpoints.js
 *      API_BASE_URL=http://localhost:8000 node profile_all_endpoints.js
 */

const http = require('http');
const https = require('https');

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';
const USERNAME = 'admin';
const PASSWORD = '6foot7foot';
const REQUEST_TIMEOUT_MS = 120000;
const PAGE_SIZE = 5;

function formEncode(obj) {
  return Object.entries(obj)
    .map(([k, v]) => encodeURIComponent(k) + '=' + encodeURIComponent(String(v)))
    .join('&');
}

function request(method, url, body = null, token = null, useFormEncoded = false) {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https://');
    const client = isHttps ? https : http;
    const urlObj = new URL(url);
    const payload = body == null ? null : useFormEncoded ? formEncode(body) : JSON.stringify(body);
    const options = {
      hostname: urlObj.hostname,
      port: urlObj.port || (isHttps ? 443 : 80),
      path: urlObj.pathname + urlObj.search,
      method,
      headers: {
        'Accept': 'application/json',
        'Content-Type': useFormEncoded ? 'application/x-www-form-urlencoded' : 'application/json',
        'Connection': 'close',
      },
    };
    if (payload) options.headers['Content-Length'] = Buffer.byteLength(payload, 'utf8');
    if (token) options.headers['Authorization'] = `Token ${token}`;

    const req = client.request(options, (res) => {
      clearTimeout(timer);
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode >= 301 && res.statusCode <= 303 && res.headers.location) {
          request(method, new URL(res.headers.location, url).href, body, token, useFormEncoded).then(resolve).catch(reject);
          return;
        }
        try {
          resolve({ status: res.statusCode, data: data ? JSON.parse(data) : null });
        } catch {
          resolve({ status: res.statusCode, data });
        }
      });
    });
    req.on('error', (err) => {
      clearTimeout(timer);
      reject(err);
    });
    const timer = setTimeout(() => {
      req.destroy();
      reject(new Error(`Request timeout after ${REQUEST_TIMEOUT_MS}ms`));
    }, REQUEST_TIMEOUT_MS);
    if (payload) req.write(payload);
    req.end();
  });
}

async function requestWithRetry(method, url, body, token, useFormEncoded, maxRetries = 2) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await request(method, url, body, token, useFormEncoded);
    } catch (err) {
      const isReset = err.code === 'ECONNRESET' || err.code === 'ECONNREFUSED' || err.syscall === 'read';
      if (isReset && attempt < maxRetries) {
        console.log(`  (retry ${attempt}/${maxRetries}...)`);
        await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      throw err;
    }
  }
}

function getList(data) {
  return data?.results ?? (Array.isArray(data) ? data : []);
}

async function hit(name, url, token = null) {
  const res = await requestWithRetry('GET', url, null, token);
  console.log(`  ${name}: ${res.status}`);
  return res;
}

async function main() {
  console.log('API Base URL:', API_BASE_URL);
  console.log('Logging in as admin...\n');

  const loginUrl = `${API_BASE_URL}/api/auth/token/login/`;
  const loginRes = await request('POST', loginUrl, { username: USERNAME, password: PASSWORD }, null, true);
  if (loginRes.status !== 200) {
    console.error('Login failed:', loginRes.status, loginRes.data);
    process.exit(1);
  }
  const token = loginRes.data?.token;
  if (!token) {
    console.error('No token in response:', loginRes.data);
    process.exit(1);
  }
  console.log('Login OK.\n');

  const base = API_BASE_URL;
  const inv = `${base}/api/inventory`;
  const pub = `${base}/api/v1/public`;

  // ---------- API INVENTORY (admin/customer) ----------
  console.log('--- api/inventory/ (authenticated) ---\n');

  // Products
  await hit('GET products list', `${inv}/products/?page_size=${PAGE_SIZE}`, token);
  let listRes = await requestWithRetry('GET', `${inv}/products/?page_size=1`, null, token);
  const productId = getList(listRes.data)?.[0]?.id;
  if (productId) {
    await hit('GET product detail', `${inv}/products/${productId}/`, token);
    await hit('GET product stock-summary', `${inv}/products/${productId}/stock-summary/`, token);
    await hit('GET product available-units', `${inv}/products/${productId}/available-units/`, token);
  }

  // Images, unit-images, units
  await hit('GET images list', `${inv}/images/?page_size=${PAGE_SIZE}`, token);
  await hit('GET unit-images list', `${inv}/unit-images/?page_size=${PAGE_SIZE}`, token);
  await hit('GET units list', `${inv}/units/?page_size=${PAGE_SIZE}`, token);
  listRes = await requestWithRetry('GET', `${inv}/units/?page_size=1`, null, token);
  const unitId = getList(listRes.data)?.[0]?.id;
  if (unitId) await hit('GET unit detail', `${inv}/units/${unitId}/`, token);

  // Reviews, orders, order-items, delivery-rates
  await hit('GET reviews list', `${inv}/reviews/?page_size=${PAGE_SIZE}`, token);
  await hit('GET orders list', `${inv}/orders/?page_size=${PAGE_SIZE}`, token);
  listRes = await requestWithRetry('GET', `${inv}/orders/?page_size=1`, null, token);
  const orderId = getList(listRes.data)?.[0]?.order_id ?? getList(listRes.data)?.[0]?.id;
  if (orderId) {
    await hit('GET order detail', `${inv}/orders/${orderId}/`, token);
    await hit('GET order payment_status', `${inv}/orders/${orderId}/payment_status/`, token);
    await hit('GET order receipt', `${inv}/orders/${orderId}/receipt/`, token);
  }
  await hit('GET order-items list', `${inv}/order-items/?page_size=${PAGE_SIZE}`, token);
  await hit('GET delivery-rates list', `${inv}/delivery-rates/`, token);

  // Lookup tables
  await hit('GET colors list', `${inv}/colors/`, token);
  await hit('GET sources list', `${inv}/sources/`, token);
  await hit('GET accessories-link list', `${inv}/accessories-link/?page_size=${PAGE_SIZE}`, token);
  await hit('GET tags list', `${inv}/tags/`, token);

  // Admin
  await hit('GET admin-roles list', `${inv}/admin-roles/`, token);
  await hit('GET admins list', `${inv}/admins/?page_size=${PAGE_SIZE}`, token);

  // Request management
  await hit('GET reservation-requests list', `${inv}/reservation-requests/?page_size=${PAGE_SIZE}`, token);
  await hit('GET return-requests list', `${inv}/return-requests/?page_size=${PAGE_SIZE}`, token);
  await hit('GET unit-transfers list', `${inv}/unit-transfers/?page_size=${PAGE_SIZE}`, token);
  await hit('GET notifications list', `${inv}/notifications/?page_size=${PAGE_SIZE}`, token);
  await hit('GET notifications unread_count', `${inv}/notifications/unread_count/`, token);

  // Reports (list not applicable; only custom actions)
  await hit('GET reports inventory_value', `${inv}/reports/inventory_value/`, token);
  await hit('GET reports stock_movement', `${inv}/reports/stock_movement/?days=7`, token);
  await hit('GET reports product_performance', `${inv}/reports/product_performance/`, token);
  await hit('GET reports aging_inventory', `${inv}/reports/aging_inventory/?days=30`, token);
  await hit('GET reports salesperson_performance', `${inv}/reports/salesperson_performance/?days=30`, token);
  await hit('GET reports request_management', `${inv}/reports/request_management/?days=30`, token);

  // Audit, stock-alerts, brands, leads, promotions, bundles
  await hit('GET audit-logs list', `${inv}/audit-logs/?page_size=${PAGE_SIZE}`, token);
  await hit('GET stock-alerts list', `${inv}/stock-alerts/?page_size=${PAGE_SIZE}`, token);
  await hit('GET brands list', `${inv}/brands/?page_size=${PAGE_SIZE}`, token);
  await hit('GET leads list', `${inv}/leads/?page_size=${PAGE_SIZE}`, token);
  await hit('GET promotion-types list', `${inv}/promotion-types/`, token);
  await hit('GET promotions list', `${inv}/promotions/?page_size=${PAGE_SIZE}`, token);
  await hit('GET bundles list', `${inv}/bundles/?page_size=${PAGE_SIZE}`, token);
  await hit('GET bundle-items list', `${inv}/bundle-items/?page_size=${PAGE_SIZE}`, token);

  // Custom GET paths under api/inventory/
  await hit('GET profiles admin', `${inv}/profiles/admin/`, token);
  await hit('GET profiles customer', `${inv}/profiles/customer/`, token);
  await hit('GET phone-search (inventory)', `${inv}/phone-search/?min_price=10000&max_price=100000`, token);
  await hit('GET utils discount-calculator', `${inv}/utils/discount-calculator/?price=10000&discount_percent=10`, token);
  await hit('GET units/available', `${inv}/units/available/`, token);

  // ---------- API V1 PUBLIC (no auth) ----------
  console.log('\n--- api/v1/public/ (no auth) ---\n');

  await hit('GET public products list', `${pub}/products/?page_size=${PAGE_SIZE}`, null);
  listRes = await requestWithRetry('GET', `${pub}/products/?page_size=1`, null, null);
  const pubProductId = getList(listRes.data)?.[0]?.id ?? productId;
  if (pubProductId) {
    await hit('GET public product detail', `${pub}/products/${pubProductId}/`, null);
    await hit('GET public product units', `${pub}/products/${pubProductId}/units/`, null);
  }
  await hit('GET public products brands', `${pub}/products/brands/`, null);
  await hit('GET public products review-summary', pubProductId ? `${pub}/products/review-summary/?id=${pubProductId}` : `${pub}/products/review-summary/`, null);

  await hit('GET public cart list', `${pub}/cart/`, null);
  await hit('GET public promotions list', `${pub}/promotions/?page_size=${PAGE_SIZE}`, null);
  await hit('GET public bundles list', `${pub}/bundles/?page_size=${PAGE_SIZE}`, null);
  await hit('GET public wishlist list', `${pub}/wishlist/`, null); // may 401 if no session
  await hit('GET public delivery-rates list', `${pub}/delivery-rates/`, null);
  await hit('GET public accessories-link list', `${pub}/accessories-link/?page_size=${PAGE_SIZE}`, null);
  await hit('GET public reviews list', `${pub}/reviews/?page_size=${PAGE_SIZE}`, null);
  await hit('GET public orders/history', `${pub}/orders/history/`, null); // may require params
  await hit('GET public phone-search', `${pub}/phone-search/?min_price=10000&max_price=100000`, null);

  // API root
  await hit('GET api root', base + '/', null);

  console.log('\nDone. Check /silk/ for query counts.');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
