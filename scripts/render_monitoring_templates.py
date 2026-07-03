"""
Render Jinja2-style templates for the monitoring stack.
Called by deploy-monitoring.sh — avoids sed escaping issues with passwords/tokens.
"""

import re
import shutil
import sys

TEMPLATES_DIR = sys.argv[1]
WORK_DIR = sys.argv[2]
COMPOSE_ROOT = sys.argv[3]
CLOUD_PROVIDER = sys.argv[4] if sys.argv[4] in ("aws", "gcp") else "gcp"
GCP_PROJECT_ID = sys.argv[4] if CLOUD_PROVIDER == "gcp" else ""
GRAFANA_ADMIN_PASSWORD = sys.argv[5]
GRAFANA_SMTP_USER = sys.argv[6]
GRAFANA_SMTP_PASSWORD = sys.argv[7]
GRAFANA_SMTP_FROM = sys.argv[8]
CLOUDFLARE_TUNNEL_TOKEN = sys.argv[9]
DJANGO_API_TOKEN = sys.argv[10]
PROMETHEUS_API_TARGET = sys.argv[11] if len(sys.argv) > 11 else "127.0.0.1:8000"
DEPLOY_ENV = sys.argv[12] if len(sys.argv) > 12 else "production"


def render_j2(src, dst, subs):
    with open(src) as f:
        content = f.read()
    for key, val in subs.items():
        # Replace {{ key }}
        content = content.replace("{{ " + key + " }}", str(val))
        # Replace {{ key | default('...') }} (single or double quotes)
        content = re.sub(
            r"\{\{ " + re.escape(key) + r' \| default\(["\'].*?["\']\) \}\}',
            str(val),
            content,
        )
    with open(dst, "w") as f:
        f.write(content)


# ── prometheus.yml ────────────────────────────────────────────────────────────
if CLOUD_PROVIDER == "aws":
    prometheus = f"""global:
  scrape_interval:     15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

rule_files:
  - 'alerts.yml'

scrape_configs:
  - job_name: 'django'
    scrape_interval: 10s
    metrics_path: /metrics/
    scheme: http
    static_configs:
      - targets: ['{PROMETHEUS_API_TARGET}']
        labels:
          service: django-api
          environment: {DEPLOY_ENV}

  - job_name: 'monitoring-vm'
    scrape_interval: 15s
    static_configs:
      - targets: ['localhost:9090']
"""
    with open(f"{WORK_DIR}/prometheus.yml", "w") as f:
        f.write(prometheus)
else:
    render_j2(
        f"{TEMPLATES_DIR}/prometheus.yml.j2",
        f"{WORK_DIR}/prometheus.yml",
        {
            "gcp_project_id": GCP_PROJECT_ID,
            "prometheus_api_target": PROMETHEUS_API_TARGET,
            "deploy_s3_prefix": DEPLOY_ENV,
            "env_name": DEPLOY_ENV,
            "api_public_host": PROMETHEUS_API_TARGET,
        },
    )

# ── grafana.env ──────────────────────────────────────────────────────────────
render_j2(
    f"{TEMPLATES_DIR}/grafana.env.j2",
    f"{WORK_DIR}/grafana.env",
    {
        "grafana_admin_password": GRAFANA_ADMIN_PASSWORD,
        "grafana_smtp_user": GRAFANA_SMTP_USER,
        "grafana_smtp_password": GRAFANA_SMTP_PASSWORD,
        "grafana_smtp_from": GRAFANA_SMTP_FROM,
        "django_admin_token": DJANGO_API_TOKEN,
    },
)

# ── tunnel.env ───────────────────────────────────────────────────────────────
with open(f"{WORK_DIR}/tunnel.env", "w") as f:
    f.write(f"CLOUDFLARE_TUNNEL_TOKEN={CLOUDFLARE_TUNNEL_TOKEN}\n")

# ── docker-compose files ─────────────────────────────────────────────────────
render_j2(
    f"{TEMPLATES_DIR}/docker-compose.monitoring.yml.j2",
    f"{WORK_DIR}/docker-compose.monitoring.yml",
    {"compose_root": COMPOSE_ROOT},
)

render_j2(
    f"{TEMPLATES_DIR}/tunnel-compose.yml.j2",
    f"{WORK_DIR}/docker-compose.tunnel.yml",
    {"compose_root": COMPOSE_ROOT},
)

# ── static files ─────────────────────────────────────────────────────────────
shutil.copy2(f"{TEMPLATES_DIR}/../files/datasource.yml", f"{WORK_DIR}/datasource.yml")
shutil.copy2(f"{TEMPLATES_DIR}/../files/dashboards.yml", f"{WORK_DIR}/dashboards.yml")
shutil.copy2(f"{TEMPLATES_DIR}/../files/alerts.yml", f"{WORK_DIR}/alerts.yml")
shutil.copy2(f"{TEMPLATES_DIR}/../files/django-dashboard.json", f"{WORK_DIR}/django-dashboard.json")
shutil.copy2(
    f"{TEMPLATES_DIR}/../files/executive-kpi-dashboard.json",
    f"{WORK_DIR}/executive-kpi-dashboard.json",
)
shutil.copy2(
    f"{TEMPLATES_DIR}/../files/daily-performance-dashboard.json",
    f"{WORK_DIR}/daily-performance-dashboard.json",
)
shutil.copy2(
    f"{TEMPLATES_DIR}/../files/marketing-funnel.json",
    f"{WORK_DIR}/marketing-funnel.json",
)
