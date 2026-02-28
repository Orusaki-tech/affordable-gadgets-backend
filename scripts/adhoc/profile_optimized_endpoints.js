/**
 * Hits all endpoints we optimized (stock-summary, return-requests, orders, products list)
 * plus the public products API so you can verify query counts in Django Silk.
 *
 * Uses: admin / 6foot7foot for admin endpoints; public endpoints are unauthenticated.
 *
 * Run from backend repo (or set API_BASE_URL):
 *   node profile_optimized_endpoints.js
 *   API_BASE_URL=http://localhost:8000 node profile_optimized_endpoints.js
 */

const http = require('http');
const https = require('https');

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';
const USERNAME = 'admin';
const PASSWORD = '6foot7foot';
const REQUEST_TIMEOUT_MS = 120000;

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
        console.log(`  (retry ${attempt}/${maxRetries} in 2s...)`);
        await new Promise((r) => setTimeout(r, 2000));
        continue;
      }
      throw err;
    }
  }
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
  console.log('Login OK, token received.\n');

  const endpoints = [];

  // 1. Products list (optimized: get_seo_score uses prefetched images)
  const productsListUrl = `${API_BASE_URL}/api/inventory/products/?page_size=10`;
  console.log('GET', productsListUrl);
  const listRes = await requestWithRetry('GET', productsListUrl, null, token);
  console.log('  Status:', listRes.status);
  if (listRes.data?.results) {
    console.log('  Products:', listRes.data.results.length, '(total:', listRes.data.count ?? 'N/A', ')');
  }
  endpoints.push({ name: 'Products list', path: '/api/inventory/products/?page_size=10' });
  console.log('');

  // 2. Product detail (same prefetch)
  let productId = listRes.data?.results?.[0]?.id;
  if (productId) {
    const productDetailUrl = `${API_BASE_URL}/api/inventory/products/${productId}/`;
    console.log('GET', productDetailUrl);
    const detailRes = await requestWithRetry('GET', productDetailUrl, null, token);
    console.log('  Status:', detailRes.status);
    endpoints.push({ name: 'Product detail', path: `/api/inventory/products/${productId}/` });
  } else {
    console.log('(Skip product detail: no products in list)');
  }
  console.log('');

  // 3. Stock summary (optimized: no prefetch for this action, single aggregate)
  if (productId) {
    const stockSummaryUrl = `${API_BASE_URL}/api/inventory/products/${productId}/stock-summary/`;
    console.log('GET', stockSummaryUrl);
    const stockRes = await requestWithRetry('GET', stockSummaryUrl, null, token);
    console.log('  Status:', stockRes.status);
    if (stockRes.data) {
      console.log('  available_stock:', stockRes.data.available_stock, 'min_price:', stockRes.data.min_price, 'max_price:', stockRes.data.max_price);
    }
    endpoints.push({ name: 'Stock summary', path: `/api/inventory/products/${productId}/stock-summary/` });
  }
  console.log('');

  // 4. Return requests list (optimized: prefetch units+transfers, batched net_holdings)
  const returnRequestsUrl = `${API_BASE_URL}/api/inventory/return-requests/`;
  console.log('GET', returnRequestsUrl);
  const returnRes = await requestWithRetry('GET', returnRequestsUrl, null, token);
  console.log('  Status:', returnRes.status);
  if (returnRes.data?.results) {
    console.log('  Return requests:', returnRes.data.results.length, '(total:', returnRes.data.count ?? 'N/A', ')');
  } else if (Array.isArray(returnRes.data)) {
    console.log('  Return requests:', returnRes.data.length);
  }
  endpoints.push({ name: 'Return requests list', path: '/api/inventory/return-requests/' });
  console.log('');

  // 5. Orders list (optimized: select_related('user') for OrderSerializer)
  const ordersUrl = `${API_BASE_URL}/api/inventory/orders/?page_size=10`;
  console.log('GET', ordersUrl);
  const ordersRes = await requestWithRetry('GET', ordersUrl, null, token);
  console.log('  Status:', ordersRes.status);
  if (ordersRes.data?.results) {
    console.log('  Orders:', ordersRes.data.results.length, '(total:', ordersRes.data.count ?? 'N/A', ')');
  } else if (Array.isArray(ordersRes.data)) {
    console.log('  Orders:', ordersRes.data.length);
  }
  endpoints.push({ name: 'Orders list', path: '/api/inventory/orders/?page_size=10' });
  console.log('');

  // --- Public API (no auth) ---
  console.log('--- Public products API (no auth) ---\n');

  // 6. Public products list
  const publicProductsListUrl = `${API_BASE_URL}/api/v1/public/products/?page_size=10`;
  console.log('GET', publicProductsListUrl);
  const publicListRes = await requestWithRetry('GET', publicProductsListUrl, null, null);
  console.log('  Status:', publicListRes.status);
  const publicResults = publicListRes.data?.results ?? (Array.isArray(publicListRes.data) ? publicListRes.data : []);
  if (publicResults.length) {
    console.log('  Products:', publicResults.length, publicListRes.data?.count != null ? `(total: ${publicListRes.data.count})` : '');
  }
  endpoints.push({ name: 'Public products list', path: '/api/v1/public/products/?page_size=10' });
  console.log('');

  // 7. Public product detail (use first product id from public list, or fallback to admin productId)
  const publicProductId = publicResults[0]?.id ?? productId;
  if (publicProductId) {
    const publicDetailUrl = `${API_BASE_URL}/api/v1/public/products/${publicProductId}/`;
    console.log('GET', publicDetailUrl);
    const publicDetailRes = await requestWithRetry('GET', publicDetailUrl, null, null);
    console.log('  Status:', publicDetailRes.status);
    endpoints.push({ name: 'Public product detail', path: `/api/v1/public/products/${publicProductId}/` });
    console.log('');

    // 8. Public product units
    const publicUnitsUrl = `${API_BASE_URL}/api/v1/public/products/${publicProductId}/units/`;
    console.log('GET', publicUnitsUrl);
    const publicUnitsRes = await requestWithRetry('GET', publicUnitsUrl, null, null);
    console.log('  Status:', publicUnitsRes.status);
    const unitsResults = publicUnitsRes.data?.results ?? (Array.isArray(publicUnitsRes.data) ? publicUnitsRes.data : []);
    if (unitsResults.length !== undefined) {
      console.log('  Units:', unitsResults.length);
    }
    endpoints.push({ name: 'Public product units', path: `/api/v1/public/products/${publicProductId}/units/` });
  } else {
    console.log('(Skip public product detail/units: no product id available)');
  }

  console.log('\n--- Summary: endpoints hit (check Silk for query counts) ---');
  endpoints.forEach((e, i) => console.log(`  ${i + 1}. ${e.name}: ${e.path}`));
  console.log('\nDone. Check /silk/ for these requests.');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
