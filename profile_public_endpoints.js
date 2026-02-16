/**
 * Hit PUBLIC API endpoints so you can inspect profiler output.
 * No authentication; uses /api/v1/public/ only.
 *
 * Run: node profile_public_endpoints.js
 *      API_BASE_URL=http://localhost:8000 node profile_public_endpoints.js
 */

const { API_BASE_URL, request, requestWithRetry } = require('./profile_request_shared.js');

const PUBLIC_BASE = `${API_BASE_URL}/api/v1/public`;

async function main() {
  console.log('API Base URL:', API_BASE_URL);
  console.log('Public API:', PUBLIC_BASE);
  console.log('(no auth)\n');

  // Products list
  const productsUrl = `${PUBLIC_BASE}/products/?page_size=10`;
  console.log('GET', productsUrl);
  const listRes = await requestWithRetry('GET', productsUrl);
  console.log('Status:', listRes.status);
  if (listRes.data?.results) {
    console.log('Products count:', listRes.data.results.length, '(total:', listRes.data.count ?? 'N/A', ')');
  }
  console.log('');

  // Products page 2
  const page2Url = `${PUBLIC_BASE}/products/?page=2&page_size=5`;
  console.log('GET', page2Url);
  const page2Res = await requestWithRetry('GET', page2Url);
  console.log('Status:', page2Res.status);
  console.log('');

  // First product detail (if any)
  if (listRes.data?.results?.[0]?.id) {
    const productId = listRes.data.results[0].id;
    const detailUrl = `${PUBLIC_BASE}/products/${productId}/`;
    console.log('GET', detailUrl);
    const detailRes = await requestWithRetry('GET', detailUrl);
    console.log('Status:', detailRes.status);
  }
  console.log('');

  // Optional: delivery rates, promotions (lightweight)
  console.log('GET', `${PUBLIC_BASE}/delivery-rates/`);
  const deliveryRes = await requestWithRetry('GET', `${PUBLIC_BASE}/delivery-rates/`);
  console.log('Status:', deliveryRes.status);

  console.log('\nDone. Check your profiler (e.g. /silk/) for these public requests.');
}

if (require.main === module) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
module.exports = { main };
