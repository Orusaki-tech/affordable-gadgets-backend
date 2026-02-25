#!/usr/bin/env python3
"""
Check whether slow responses are due to cold start or slow backend (query/code).

Uses the X-Processing-Ms response header added by RequestTimingMiddleware:
- Total elapsed ≈ TTFB (time until first byte; for small responses, close to full response time).
- X-Processing-Ms = time spent inside Django only.
- Cold start (time before Django received the request) ≈ elapsed - (X-Processing-Ms / 1000).

Usage:
  # Use BACKEND_URL env or pass as first argument (default: local)
  export BACKEND_URL=https://your-backend.railway.app
  python scripts/check_cold_start.py

  python scripts/check_cold_start.py https://your-backend.railway.app

  # Optional: hit a specific path (default: products list)
  python scripts/check_cold_start.py https://your-backend.railway.app /api/v1/public/products/brands/

  # Run twice (first = cold, second = warm) and compare
  python scripts/check_cold_start.py --twice
"""
import argparse
import os
import sys
import time

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

DEFAULT_BASE = "http://127.0.0.1:8000"
DEFAULT_PATH = "/api/v1/public/products/?page=1&page_size=12"


def run_one(url):
    """Return (elapsed_s, status_code, processing_ms or None)."""
    start = time.perf_counter()
    r = requests.get(url, timeout=120)
    elapsed = time.perf_counter() - start
    raw = r.headers.get("X-Processing-Ms", "").strip()
    try:
        processing_ms = int(raw) if raw else None
    except ValueError:
        processing_ms = None
    return elapsed, r.status_code, processing_ms


def print_result(label, elapsed_s, status_code, processing_ms):
    elapsed_ms = elapsed_s * 1000
    print(f"  HTTP status:        {status_code}")
    print(f"  Total elapsed:      {elapsed_s:.2f} s  ({elapsed_ms:.0f} ms)")
    if processing_ms is not None:
        processing_s = processing_ms / 1000
        cold_start_s = max(0, elapsed_s - processing_s)
        cold_start_pct = (cold_start_s / elapsed_s * 100) if elapsed_s > 0 else 0
        print(f"  X-Processing-Ms:   {processing_ms} ms  (time inside Django)")
        print(f"  Inferred cold start: {cold_start_s:.2f} s  ({cold_start_pct:.0f}% of total)")
        print()
        if cold_start_pct >= 70:
            print(f"  Verdict: LIKELY COLD START — most time was before Django received the request.")
        elif cold_start_pct <= 20 and elapsed_s > 5:
            print(f"  Verdict: LIKELY SLOW BACKEND — most time was inside Django (query/serialization).")
        else:
            print(f"  Verdict: MIXED — check Django logs.")
    else:
        print("  X-Processing-Ms:   (not present — ensure RequestTimingMiddleware is deployed)")
        print("  Verdict: Add RequestTimingMiddleware and redeploy to get cold start vs backend breakdown.")
    return processing_ms is not None


def main():
    parser = argparse.ArgumentParser(description="Check cold start vs backend slowness via X-Processing-Ms.")
    parser.add_argument("base_url", nargs="?", default=os.environ.get("BACKEND_URL", DEFAULT_BASE),
                        help="Backend base URL (or set BACKEND_URL)")
    parser.add_argument("path", nargs="?", default=DEFAULT_PATH, help="API path")
    parser.add_argument("--twice", action="store_true", help="Run request twice and compare (cold vs warm)")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    url = f"{base}{args.path}"

    if args.twice:
        print("=== First request (often cold after idle) ===")
        print(f"URL: {url}\n")
        elapsed1, status1, proc1 = run_one(url)
        print_result("First", elapsed1, status1, proc1)
        print("\n--- Second request (warm, immediately after) ---\n")
        elapsed2, status2, proc2 = run_one(url)
        print_result("Second", elapsed2, status2, proc2)
        print("\n=== Comparison ===")
        print(f"  First:  {elapsed1:.2f} s  (X-Processing-Ms: {proc1 or 'N/A'})")
        print(f"  Second: {elapsed2:.2f} s  (X-Processing-Ms: {proc2 or 'N/A'})")
        if elapsed1 > 5 and elapsed2 < elapsed1 * 0.5:
            print("  => First was much slower → consistent with COLD START (second was warm).")
        elif elapsed1 > 5 and elapsed2 > 5 and (proc1 and proc2 and proc2 > proc1 * 0.8):
            print("  => Both slow with similar X-Processing-Ms → LIKELY SLOW BACKEND (query).")
        else:
            print("  => Compare X-Processing-Ms: if first has large elapsed but small X-Processing-Ms, cold start.")
        return

    print(f"Requesting: {url}")
    print("Measuring total time and X-Processing-Ms header...\n")

    try:
        elapsed, status_code, processing_ms = run_one(url)
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        sys.exit(1)

    print("Results:")
    print_result("", elapsed, status_code, processing_ms)


if __name__ == "__main__":
    main()
