"""
Daily KPI Report Generator.
Runs on the monitoring VM: queries Prometheus + Django API, optional Grafana PNG renders.
Outputs HTML report to stdout.
"""
import base64
import datetime
import json
import os
import urllib.error
import urllib.request

PROMETHEUS = os.environ.get("PROMETHEUS_URL", "http://localhost:9090")
API_BASE = os.environ.get("DJANGO_API_BASE", "https://api.affordable-gadgetske.com").rstrip("/")
API_TOKEN = os.environ.get("DJANGO_API_TOKEN", "")
GRAFANA_URL = os.environ.get("GRAFANA_URL", "http://localhost:3000").rstrip("/")
GRAFANA_USER = os.environ.get("GRAFANA_USER", "admin")
GRAFANA_PASSWORD = os.environ.get("GRAFANA_PASSWORD", "")

GRAFANA_DASHBOARDS = [
    ("ag-marketing-funnel", "Marketing Funnel & Users"),
    ("ag-exec-kpi", "Executive KPIs"),
    ("ag-daily-perf", "Daily Performance"),
]

STYLE = """
body { font-family: system-ui, sans-serif; max-width: 960px; margin: 0 auto; color: #111; }
h1 { border-bottom: 2px solid #e5e7eb; padding-bottom: 0.4em; }
h2 { margin-top: 2em; color: #374151; border-bottom: 1px solid #e5e7eb; padding-bottom: 0.25em; }
table { width: 100%; border-collapse: collapse; margin: 0.75em 0 1.5em; font-size: 14px; }
th, td { border: 1px solid #e5e7eb; padding: 6px 10px; text-align: left; }
th { background: #f3f4f6; }
.muted { color: #6b7280; font-size: 13px; }
.dashboard-img { max-width: 100%; border: 1px solid #e5e7eb; margin: 0.5em 0 1.5em; }
.warn { color: #b45309; font-size: 13px; }
"""


def promql(query):
    url = f"{PROMETHEUS}/api/v1/query?query={urllib.request.quote(query)}"
    try:
        resp = urllib.request.urlopen(url, timeout=15).read()
        data = json.loads(resp)
        return data.get("data", {}).get("result", [])
    except Exception:
        return []


def val(metric, agg="max"):
    r = promql(f"{agg}({metric}) or vector(0)")
    return r[0]["value"][1] if r else "0"


def val_inc(metric, period="24h"):
    r = promql(f"sum(increase({metric}[{period}])) or vector(0)")
    return r[0]["value"][1] if r else "0"


def val_with_labels(metric, agg="max", label="brand"):
    r = promql(f"{agg}({metric}) by ({label}) or vector(0)")
    items = {}
    for s in r:
        items[s["metric"].get(label, "?")] = s["value"][1]
    return items


def api_get(path):
    if not API_TOKEN:
        return None
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Token {API_TOKEN}")
    req.add_header("Accept", "application/json")
    try:
        resp = urllib.request.urlopen(req, timeout=30).read()
        return json.loads(resp)
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None


def grafana_render_png(uid):
    if not GRAFANA_PASSWORD:
        return None
    params = "width=1200&height=700&from=now-24h&to=now&theme=light"
    url = f"{GRAFANA_URL}/render/d/{uid}?{params}"
    creds = base64.b64encode(f"{GRAFANA_USER}:{GRAFANA_PASSWORD}".encode()).decode()
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Basic {creds}")
    try:
        return urllib.request.urlopen(req, timeout=120).read()
    except Exception:
        return None


def esc(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def table(headers, rows):
    if not rows:
        return '<p class="muted">No data available.</p>'
    out = '<table><tr>' + "".join(f"<th>{esc(h)}</th>" for h in headers) + "</tr>"
    for row in rows:
        out += "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>"
    return out + "</table>"


def section_grafana_screenshots():
    parts = ['<h2>Grafana Dashboard Screenshots</h2>']
    if not GRAFANA_PASSWORD:
        parts.append('<p class="warn">GRAFANA_PASSWORD not set — skipping dashboard renders.</p>')
        return "".join(parts)

    for uid, title in GRAFANA_DASHBOARDS:
        parts.append(f"<h3>{esc(title)}</h3>")
        png = grafana_render_png(uid)
        if png:
            b64 = base64.b64encode(png).decode()
            parts.append(
                f'<img class="dashboard-img" alt="{esc(title)}" '
                f'src="data:image/png;base64,{b64}" />'
            )
        else:
            parts.append(
                f'<p class="warn">Render unavailable for {esc(title)}. '
                f'<a href="{esc(GRAFANA_URL)}/d/{esc(uid)}">Open in Grafana</a></p>'
            )
    return "".join(parts)


def section_marketing_funnel():
    parts = ['<h2>Marketing Funnel &amp; User Activity</h2>']
    funnel = api_get("/api/inventory/analytics/funnel-summary/")
    if funnel:
        s = funnel.get("summary", {})
        parts.append(table(
            ["Metric", "Value"],
            [
                ("Total registered users", s.get("total_users", 0)),
                ("Users with orders", s.get("users_with_orders", 0)),
                ("Users with events", s.get("unique_users_with_events", 0)),
                ("Searches (period)", s.get("total_searches", 0)),
                ("Product views (period)", s.get("total_product_views", 0)),
                ("Page views (period)", s.get("total_page_views", 0)),
            ],
        ))
        sources = funnel.get("acquisition_sources", [])[:10]
        if sources:
            parts.append("<h3>Acquisition Sources</h3>")
            parts.append(table(
                ["Source", "Users"],
                [(r.get("source", "?"), r.get("count", 0)) for r in sources],
            ))
        searches = funnel.get("popular_searches", [])[:10]
        if searches:
            parts.append("<h3>Popular Searches</h3>")
            parts.append(table(
                ["Query", "Count"],
                [(r.get("query", "?"), r.get("count", 0)) for r in searches],
            ))
    else:
        parts.append('<p class="warn">Funnel summary unavailable (check DJANGO_API_TOKEN).</p>')

    daily = api_get("/api/inventory/analytics/daily-activity/")
    if daily and daily.get("events"):
        parts.append("<h3>Today&rsquo;s Activity Feed</h3>")
        parts.append(table(
            ["Time", "User", "Event", "Product", "Detail"],
            [
                (
                    (e.get("time") or "")[:19],
                    e.get("email") or e.get("user", ""),
                    e.get("event_type", ""),
                    e.get("product", ""),
                    e.get("detail", ""),
                )
                for e in daily["events"][:25]
            ],
        ))

    users = api_get("/api/inventory/analytics/daily-users/")
    if users and users.get("users"):
        parts.append("<h3>Today&rsquo;s Active Users</h3>")
        parts.append(table(
            ["Email", "Phone", "Events", "Searches", "Products Viewed", "Cart Adds", "Last Seen"],
            [
                (
                    u.get("email", ""),
                    u.get("phone", ""),
                    u.get("total_events", 0),
                    u.get("searches", ""),
                    u.get("products_viewed", ""),
                    u.get("products_added_to_cart", ""),
                    (u.get("last_seen") or "")[:19],
                )
                for u in users["users"][:20]
            ],
        ))
    return "".join(parts)


def section_orders_and_customers():
    parts = ['<h2>Recent Orders &amp; Customers</h2>']
    orders = api_get("/api/inventory/orders/?page=1")
    if orders:
        rows = orders.get("results", orders if isinstance(orders, list) else [])
        if rows:
            parts.append("<h3>Recent Orders</h3>")
            parts.append(table(
                ["Order ID", "Status", "Customer", "Phone", "Email", "Source", "Created"],
                [
                    (
                        str(o.get("order_id", ""))[:8] + "…",
                        o.get("status_display") or o.get("status", ""),
                        o.get("customer_username", ""),
                        o.get("customer_phone", ""),
                        o.get("customer_email", ""),
                        o.get("order_source_display") or o.get("order_source", ""),
                        (o.get("created_at") or "")[:19],
                    )
                    for o in rows[:20]
                ],
            ))

    registered = api_get("/api/inventory/analytics/registered-users/")
    if registered and registered.get("users"):
        parts.append("<h3>Registered Users (lifetime activity)</h3>")
        parts.append(table(
            ["Email", "Phone", "Joined", "Last Login", "Events", "Last Seen"],
            [
                (
                    u.get("email", ""),
                    u.get("phone", ""),
                    (u.get("date_joined") or "")[:10],
                    (u.get("last_login") or "")[:19],
                    u.get("total_events", 0),
                    (u.get("last_seen") or "")[:19],
                )
                for u in registered["users"][:25]
            ],
        ))
    return "".join(parts)


def section_blogs():
    parts = ['<h2>Blog / Buying Guides</h2>']
    blog = api_get("/api/inventory/analytics/blog-summary/")
    if not blog:
        return parts[0] + '<p class="warn">Blog summary unavailable.</p>'
    parts.append(table(
        ["Metric", "Count"],
        [
            ("Published articles", blog.get("published_count", 0)),
            ("Draft articles", blog.get("draft_count", 0)),
        ],
    ))
    articles = blog.get("recent_articles", [])
    if articles:
        parts.append("<h3>Recently Updated Articles</h3>")
        parts.append(table(
            ["Product", "Headline", "Published", "Updated"],
            [
                (
                    a.get("product_name", ""),
                    (a.get("headline") or "")[:60],
                    "Yes" if a.get("is_published") else "No",
                    (a.get("updated_at") or "")[:19],
                )
                for a in articles
            ],
        ))
    return "".join(parts)


def section_inventory():
    parts = ['<h2>Inventory (SKU / Product Level)</h2>']
    inv = api_get("/api/inventory/reports/inventory_value/")
    if inv:
        parts.append(table(
            ["Metric", "Value (KES)"],
            [
                ("Total inventory value", inv.get("total_value", 0)),
                ("Available (AV) value", inv.get("available_value", 0)),
            ],
        ))
        by_product = inv.get("by_product", [])[:20]
        if by_product:
            parts.append("<h3>Top Products by Inventory Value</h3>")
            parts.append(table(
                ["Product", "Type", "Units", "Available", "Total Value (KES)"],
                [
                    (
                        p.get("product_template__product_name", ""),
                        p.get("product_template__product_type", ""),
                        p.get("unit_count", 0),
                        p.get("available_count", 0),
                        p.get("total_value", 0),
                    )
                    for p in by_product
                ],
            ))

    perf = api_get("/api/inventory/reports/product_performance/")
    if perf:
        rows = perf[:15] if isinstance(perf, list) else []
        if rows:
            parts.append("<h3>Product Performance</h3>")
            parts.append(table(
                ["Product", "Total", "Available", "Sold", "Sell-through %", "Revenue (KES)"],
                [
                    (
                        p.get("product_name", ""),
                        p.get("total_units", 0),
                        p.get("available_units", 0),
                        p.get("sold_units", 0),
                        p.get("sell_through_rate", 0),
                        p.get("total_revenue", 0),
                    )
                    for p in rows
                ],
            ))

    units = api_get("/api/inventory/units/?sale_status=AV&page=1")
    if units:
        unit_rows = units.get("results", [])
        if unit_rows:
            parts.append("<h3>Available Units (sample)</h3>")
            parts.append(table(
                ["Serial", "Product", "Status", "Price (KES)"],
                [
                    (
                        u.get("serial_number", ""),
                        u.get("product_template_name", ""),
                        u.get("sale_status", ""),
                        u.get("selling_price", ""),
                    )
                    for u in unit_rows[:25]
                ],
            ))
    return "".join(parts)


def section_salesperson():
    parts = ['<h2>Salesperson Performance (30 days)</h2>']
    perf = api_get("/api/inventory/reports/salesperson_performance/?days=30")
    if not perf:
        return parts[0] + '<p class="warn">Salesperson report unavailable.</p>'
    rows = perf if isinstance(perf, list) else []
    if not rows:
        return parts[0] + '<p class="muted">No salesperson data for this period.</p>'
    parts.append(table(
        ["Name", "Email", "Reservations", "Approved", "Approval %", "Returns", "Transfers"],
        [
            (
                p.get("salesperson_name", ""),
                p.get("salesperson_email", ""),
                p.get("reservations_requested", 0),
                p.get("reservations_approved", 0),
                p.get("approval_rate", 0),
                p.get("returns_requested", 0),
                p.get("transfers_requested", 0),
            )
            for p in rows
        ],
    ))
    return "".join(parts)


def section_prometheus_kpis():
    today = datetime.date.today().isoformat()
    rev_24h = val_inc("revenue_earned_cumulative")
    orders_24h = val_inc("orders_created_cumulative")
    leads_24h = val_inc("leads_created_cumulative")
    conv_24h = val_inc("leads_converted_cumulative")
    cust_24h = val_inc("customers_registered_cumulative")
    try:
        lead_rate = f"{round(float(conv_24h) / max(float(leads_24h), 1) * 100, 1)}%"
    except (TypeError, ValueError):
        lead_rate = "0%"

    active_carts = val("cart_active_carts")
    stale_carts = val("cart_stale_carts")
    inventory = val('inventory_value_total{status="AV"}')
    carts_total = val('carts_total{status="total"}')
    customers = val("customers_total")
    app_instances = val("app_instances_active")
    active_users = val("active_users")

    today_popular = promql("sort_desc(max(cart_popular_items) by (product_name))")
    today_items = [
        (s["metric"].get("product_name", "?"), s["value"][1]) for s in today_popular[:5]
    ]
    yesterday_popular = promql(
        "sort_desc(max(cart_popular_items offset 24h) by (product_name))"
    )
    yesterday_items = {
        s["metric"].get("product_name", "?"): s["value"][1] for s in yesterday_popular
    }
    orders_by_status = val_with_labels("orders_by_status", agg="max", label="status")

    parts = [f"<h1>KPI Report — {esc(today)}</h1>"]
    parts.append("<h2>Period Metrics (24h change)</h2>")
    parts.append(table(
        ["Metric", "Value"],
        [
            ("Revenue (24h)", f"{rev_24h} KES"),
            ("Orders Created (24h)", orders_24h),
            ("New Leads (24h)", leads_24h),
            ("Conversions (24h)", conv_24h),
            ("New Customers (24h)", cust_24h),
            ("Lead Conv. Rate (24h)", lead_rate),
        ],
    ))
    parts.append("<h2>Current State (Prometheus)</h2>")
    parts.append(table(
        ["Metric", "Value"],
        [
            ("Active Carts", active_carts),
            ("Stale Carts (>2h)", stale_carts),
            ("Total Carts (All Time)", carts_total),
            ("Inventory Value (AV)", f"{inventory} KES"),
            ("Customers", customers),
            ("Active Users", active_users),
            ("App Instances", app_instances),
        ],
    ))
    parts.append("<h2>Orders by Status</h2>")
    parts.append(table(
        ["Status", "Count"],
        list(orders_by_status.items()),
    ))
    parts.append("<h2>Top Items in Active Carts — Day Comparison</h2>")
    cart_rows = []
    for name, cnt in today_items:
        ycnt = int(float(yesterday_items.get(name, 0)))
        diff = int(float(cnt)) - ycnt
        arrow = "▲" if diff > 0 else ("▼" if diff < 0 else "—")
        cart_rows.append((name, cnt, ycnt, f"{arrow} {abs(diff) if diff else ''}"))
    parts.append(table(["Product", "Today", "Yesterday", "Change"], cart_rows))
    return "".join(parts)


html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Affordable Gadgets — Daily KPI Report</title>
<style>{STYLE}</style>
</head>
<body>
{section_prometheus_kpis()}
{section_grafana_screenshots()}
{section_marketing_funnel()}
{section_orders_and_customers()}
{section_blogs()}
{section_inventory()}
{section_salesperson()}
<hr>
<p class="muted">
Generated by <code>daily-kpi-report.py</code> from Prometheus, Django API, and Grafana.
</p>
</body>
</html>"""

print(html)
