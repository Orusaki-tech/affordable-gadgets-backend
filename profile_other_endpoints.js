/**
 * Hit authenticated (inventory/admin) endpoints so you can inspect profiler output.
 * Logs in as admin then calls /api/inventory/products/ etc.
 * Uses: admin / 6foot7foot
 *
 * Run: node profile_other_endpoints.js
 *      API_BASE_URL=http://localhost:8000 node profile_other_endpoints.js
 */

const { API_BASE_URL, request, requestWithRetry } = require('./profile_request_shared.js');

const USERNAME = 'admin';
const PASSWORD = '6foot7foot';
const INVENTORY_BASE = `${API_BASE_URL}/api/inventory`;

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

  // Products list (inventory API)
  const productsUrl = `${INVENTORY_BASE}/products/?page_size=10`;
  console.log('GET', productsUrl);
  const listRes = await requestWithRetry('GET', productsUrl, null, token);
  console.log('Status:', listRes.status);
  if (listRes.data?.results) {
    console.log('Products count:', listRes.data.results.length, '(total:', listRes.data.count ?? 'N/A', ')');
  }
  console.log('');

  const page2Url = `${INVENTORY_BASE}/products/?page=2&page_size=5`;
  console.log('GET', page2Url);
  const page2Res = await requestWithRetry('GET', page2Url, null, token);
  console.log('Status:', page2Res.status);
  console.log('');

  if (listRes.data?.results?.[0]?.id) {
    const productId = listRes.data.results[0].id;
    const detailUrl = `${INVENTORY_BASE}/products/${productId}/`;
    console.log('GET', detailUrl);
    const detailRes = await requestWithRetry('GET', detailUrl, null, token);
    console.log('Status:', detailRes.status);
  }

  console.log('\nDone. Check your profiler (e.g. /silk/) for these requests.');
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
module.exports = { main };
