/**
 * Runs both profile scripts in sequence: public endpoints, then authenticated.
 * For profiling only public or only inventory, run the split scripts directly:
 *
 *   node profile_public_endpoints.js   # /api/v1/public/ only, no auth
 *   node profile_other_endpoints.js    # login + /api/inventory/products/ etc.
 *
 *   node profile_products_request.js   # runs both (this file)
 *
 *   API_BASE_URL=http://localhost:8000 node profile_public_endpoints.js
 */

const { main: runPublic } = require('./profile_public_endpoints.js');
const { main: runOther } = require('./profile_other_endpoints.js');

async function main() {
  console.log('=== Public endpoints ===\n');
  await runPublic();

  console.log('\n=== Other (authenticated) endpoints ===\n');
  await runOther();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
