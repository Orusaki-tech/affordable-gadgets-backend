#!/usr/bin/env python3
"""
Executive daily report: queries Prometheus for key business & system metrics
and produces a summary suitable for Slack / email / stdout.

Usage:
  python scripts/exec_report.py                           # default http://localhost:9090
  python scripts/exec_report.py --prometheus https://user:pass@prometheus.example.com
  python scripts/exec_report.py --slack-webhook https://hooks.slack.com/...
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta


def query(prometheus_url: str, query: str) -> list:
    """Execute a Prometheus instant or range query, return result vector."""
    params = urllib.parse.urlencode({"query": query})
    url = f"{prometheus_url}/api/v1/query?{params}"
    resp = urllib.request.urlopen(url, timeout=15)
    data = json.load(resp)
    if data["status"] != "success":
        raise RuntimeError(f"Prometheus query failed: {data.get('error', 'unknown')}")
    return data["data"]["result"]


def query_range(prometheus_url: str, query: str, hours: int = 24) -> list:
    """Execute a Prometheus range query over the last N hours."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    params = urllib.parse.urlencode({
        "query": query,
        "start": start.timestamp(),
        "end": end.timestamp(),
        "step": "300",
    })
    url = f"{prometheus_url}/api/v1/query_range?{params}"
    resp = urllib.request.urlopen(url, timeout=15)
    data = json.load(resp)
    if data["status"] != "success":
        raise RuntimeError(f"Prometheus range query failed: {data.get('error', 'unknown')}")
    return data["data"]["result"]


def safe_float(val, default=0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def build_report(prometheus_url: str) -> dict:
    """Collect business + system metrics from Prometheus into a dict."""

    # ── Request rate (req/s over last 24h) ─────────────────────────
    req_rate = query(prometheus_url, "sum(rate(http_requests_total[24h]))")
    total_req_rate = safe_float(req_rate[0]["value"][1]) if req_rate else 0

    # ── Error rate (% of 5xx over last 24h) ────────────────────────
    err_rate = query(
        prometheus_url,
        'sum(rate(http_requests_total{status_code=~"5.."}[24h])) / sum(rate(http_requests_total[24h])) * 100',
    )
    error_rate_pct = safe_float(err_rate[0]["value"][1]) if err_rate else 0

    # ── P95 latency (seconds) ──────────────────────────────────────
    p95 = query(
        prometheus_url,
        'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[24h])) by (le))',
    )
    p95_latency = safe_float(p95[0]["value"][1]) if p95 else 0

    # ── Total orders (lifetime) ────────────────────────────────────
    orders = query(prometheus_url, "sum(orders_total)")
    total_orders = safe_float(orders[0]["value"][1]) if orders else 0

    # ── Orders in last 24h ─────────────────────────────────────────
    orders_24h = query(prometheus_url, "sum(increase(orders_total[24h]))")
    orders_today = safe_float(orders_24h[0]["value"][1]) if orders_24h else 0

    # ── Payment attempts (last 24h) ────────────────────────────────
    payments_24h = query(prometheus_url, 'sum(increase(payments_total[24h])) by (status)')
    payments_by_status = {p["metric"].get("status", "unknown"): safe_float(p["value"][1]) for p in payments_24h}

    # ── Active users ──────────────────────────────────────────────
    users = query(prometheus_url, "sum(active_users)")
    active_users = safe_float(users[0]["value"][1]) if users else 0

    # ── Cache hit ratio ───────────────────────────────────────────
    cache_hits = query(prometheus_url, "sum(increase(cache_hits_total[24h]))")
    cache_misses = query(prometheus_url, "sum(increase(cache_misses_total[24h]))")
    hits = safe_float(cache_hits[0]["value"][1]) if cache_hits else 0
    misses = safe_float(cache_misses[0]["value"][1]) if cache_misses else 0
    total_reqs = hits + misses
    cache_hit_ratio = (hits / total_reqs * 100) if total_reqs > 0 else 0

    # ── Top endpoints (last 24h) ──────────────────────────────────
    top_endpoints = query(
        prometheus_url,
        'topk(10, sum(rate(http_requests_total[24h])) by (endpoint))',
    )
    top_routes = [
        {"endpoint": t["metric"]["endpoint"], "rps": round(safe_float(t["value"][1]), 2)}
        for t in top_endpoints
    ]

    # ── System health ─────────────────────────────────────────────
    healthy = query(prometheus_url, 'count(up{job="django"} == 1)')
    total_instances = query(prometheus_url, 'count(up{job="django"})')
    healthy_count = int(safe_float(healthy[0]["value"][1])) if healthy else 0
    total_count = int(safe_float(total_instances[0]["value"][1])) if total_instances else 0

    # ── Memory (avg across instances) ────────────────────────────
    mem = query(prometheus_url, "avg(process_resident_memory_bytes{job='django'})")
    avg_memory_bytes = safe_float(mem[0]["value"][1]) if mem else 0

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period": "last 24 hours",
        "summary": {
            "total_orders": int(total_orders),
            "orders_today": int(orders_today),
            "request_rate_rps": round(total_req_rate, 2),
            "error_rate_pct": round(error_rate_pct, 2),
            "p95_latency_seconds": round(p95_latency, 3),
            "active_users": int(active_users),
            "cache_hit_ratio_pct": round(cache_hit_ratio, 1),
        },
        "payments": payments_by_status,
        "top_endpoints": top_routes,
        "system": {
            "healthy_instances": f"{healthy_count}/{total_count}",
            "avg_memory_mb": round(avg_memory_bytes / 1024 / 1024, 1),
        },
    }


def format_for_slack(report: dict) -> str:
    s = report["summary"]
    sys_ = report["system"]
    lines = [
        f"📊 *Daily Executive Report*",
        f"*Period:* {report['period']}",
        f"",
        f"*Business KPIs:*",
        f"  • Orders (24h): *{s['orders_today']}*  (lifetime: {s['total_orders']})",
        f"  • Request rate: *{s['request_rate_rps']} req/s*",
        f"  • Error rate: *{s['error_rate_pct']}%*",
        f"  • P95 latency: *{s['p95_latency_seconds']}s*",
        f"  • Active users: *{s['active_users']}*",
        f"  • Cache hit ratio: *{s['cache_hit_ratio_pct']}%*",
        f"",
        f"*System Health:*",
        f"  • Healthy instances: *{sys_['healthy_instances']}*",
        f"  • Avg memory: *{sys_['avg_memory_mb']} MB*",
    ]
    if report["payments"]:
        lines.append(f"")
        lines.append(f"*Payments (24h):*")
        for status, count in sorted(report["payments"].items()):
            lines.append(f"  • {status}: {int(count)}")
    if report["top_endpoints"]:
        lines.append(f"")
        lines.append(f"*Top Endpoints:*")
        for r in report["top_endpoints"][:5]:
            lines.append(f"  • {r['endpoint']}: {r['rps']} req/s")
    return "\n".join(lines)


def format_for_markdown(report: dict) -> str:
    s = report["summary"]
    sys_ = report["system"]
    lines = [
        f"# Daily Executive Report",
        f"**Period:** {report['period']}  |  **Generated:** {report['generated_at']}",
        f"",
        f"## Business KPIs",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Orders (24h) | {s['orders_today']} (lifetime: {s['total_orders']}) |",
        f"| Request rate | {s['request_rate_rps']} req/s |",
        f"| Error rate | {s['error_rate_pct']}% |",
        f"| P95 latency | {s['p95_latency_seconds']}s |",
        f"| Active users | {s['active_users']} |",
        f"| Cache hit ratio | {s['cache_hit_ratio_pct']}% |",
        f"",
        f"## System Health",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Healthy instances | {sys_['healthy_instances']} |",
        f"| Avg memory | {sys_['avg_memory_mb']} MB |",
    ]
    if report["payments"]:
        lines.append(f"")
        lines.append(f"## Payments (24h)")
        for status, count in sorted(report["payments"].items()):
            lines.append(f"- {status}: {int(count)}")
    if report["top_endpoints"]:
        lines.append(f"")
        lines.append(f"## Top Endpoints (24h)")
        for r in report["top_endpoints"][:5]:
            lines.append(f"- {r['endpoint']}: {r['rps']} req/s")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate exec report from Prometheus")
    parser.add_argument("--prometheus", default=os.environ.get("PROMETHEUS_URL", "http://localhost:9090"))
    parser.add_argument("--slack-webhook", default=os.environ.get("SLACK_WEBHOOK_URL", ""))
    parser.add_argument("--format", choices=["text", "slack", "markdown", "json"], default="slack")
    args = parser.parse_args()

    report = build_report(args.prometheus)

    if args.format == "json":
        print(json.dumps(report, indent=2))
    elif args.format == "slack":
        msg = format_for_slack(report)
        if args.slack_webhook:
            payload = json.dumps({"text": msg}).encode()
            urllib.request.urlopen(args.slack_webhook, payload, timeout=15)
            print("Report sent to Slack")
        else:
            print(msg)
    elif args.format == "markdown":
        print(format_for_markdown(report))
    else:
        s = report["summary"]
        print(f"Orders (24h): {s['orders_today']}  |  Req/s: {s['request_rate_rps']}  |  "
              f"Errors: {s['error_rate_pct']}%  |  P95: {s['p95_latency_seconds']}s  |  "
              f"Users: {s['active_users']}")


if __name__ == "__main__":
    main()
