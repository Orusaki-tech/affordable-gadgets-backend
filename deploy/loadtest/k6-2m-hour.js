/**
 * Sustained load: ~2M HTTP requests in 1 hour (556 req/s default).
 *
 *   k6 run deploy/loadtest/k6-2m-hour.js
 *   k6 run -e BASE_URL=https://api-staging.affordable-gadgetske.com deploy/loadtest/k6-2m-hour.js
 *   k6 run -e TARGET_RPS=300 -e DURATION=30m deploy/loadtest/k6-2m-hour.js
 *
 * Distributed (4 runners, each 1/4 of rate):
 *   k6 run --execution-segment "0:1/4" --execution-segment-sequence "0,1,2,3" \
 *     -e TARGET_RPS=556 -e K6_CLOUDEXECUTION_ID=run1 deploy/loadtest/k6-2m-hour.js
 */
import { trafficRequest, setupProductIds, constantRateScenario, defaultThresholds } from './lib.js';

export const options = {
  setupTimeout: '120s',
  scenarios: {
    two_million_per_hour: constantRateScenario(),
  },
  thresholds: defaultThresholds,
};

export function setup() {
  return setupProductIds();
}

export default function (data) {
  trafficRequest(data?.ids || []);
}
