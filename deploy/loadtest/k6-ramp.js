/**
 * Ramp to TARGET_RPS over 15m, hold 10m, ramp down — find sustainable ceiling.
 *
 *   k6 run -e TARGET_RPS=556 deploy/loadtest/k6-ramp.js
 */
import { trafficRequest, setupProductIds, defaultThresholds } from './lib.js';

const peak = Number(__ENV.TARGET_RPS || 556);

export const options = {
  setupTimeout: '120s',
  scenarios: {
    ramp: {
      executor: 'ramping-arrival-rate',
      startRate: Math.max(10, Math.floor(peak * 0.1)),
      timeUnit: '1s',
      preAllocatedVUs: Number(__ENV.PRE_ALLOCATED_VUS || Math.max(100, Math.ceil(peak * 0.6))),
      maxVUs: Number(__ENV.MAX_VUS || Math.max(500, peak * 4)),
      stages: [
        { duration: '5m', target: Math.floor(peak * 0.25) },
        { duration: '5m', target: Math.floor(peak * 0.5) },
        { duration: '5m', target: peak },
        { duration: '10m', target: peak },
        { duration: '3m', target: 0 },
      ],
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
