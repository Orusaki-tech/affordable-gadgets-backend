/**
 * Quick validation (~2 min, low rate). Run before the 1h soak.
 *
 *   k6 run deploy/loadtest/k6-smoke.js
 */
import { trafficRequest, setupProductIds, defaultThresholds } from './lib.js';

export const options = {
  setupTimeout: '60s',
  scenarios: {
    smoke: {
      executor: 'constant-arrival-rate',
      rate: Number(__ENV.TARGET_RPS || 20),
      timeUnit: '1s',
      duration: __ENV.DURATION || '2m',
      preAllocatedVUs: 20,
      maxVUs: 100,
    },
  },
  thresholds: defaultThresholds,
};

export function setup() {
  return setupProductIds();
}

export default function (data) {
  trafficRequest(data?.ids || []);
}
