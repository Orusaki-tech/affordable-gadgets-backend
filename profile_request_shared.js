/**
 * Shared HTTP helpers for profile scripts (public and other endpoints).
 * Used by profile_public_endpoints.js and profile_other_endpoints.js.
 */

const http = require('http');
const https = require('https');

const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000';
const REQUEST_TIMEOUT_MS = 120000; // 2 min for slow profiler

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
    if (token) {
      options.headers['Authorization'] = `Token ${token}`;
    }

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

module.exports = {
  API_BASE_URL,
  REQUEST_TIMEOUT_MS,
  formEncode,
  request,
  requestWithRetry,
};
