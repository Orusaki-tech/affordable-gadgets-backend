# Observability Investment Justification

## For: Executive Leadership
## Context: Marketing Event — 2M requests/hour

---

## The Problem (One Sentence)
Without observability, when traffic spikes during our event, **we cannot distinguish between "it's working fine" and "it's silently failing"** until customers complain — by which time we've lost revenue and trust.

## What We Implemented

| Capability | Tool | Cost | Value |
|-----------|------|------|-------|
| Error tracking | Sentry | Free tier | Know exactly what broke and where, in real-time |
| Request metrics | Prometheus | Free (OSS) | See latency, throughput, error rates live |
| Dashboards | Grafana | Free (OSS) | One screen shows the entire system health |
| Structured logging | JSON format | $0 | Machine-searchable logs, no more grep-ing |

**Total cash outlay: $0** (all open-source, Sentry free tier covers our volume)

---

## The Business Case

### 1. Without Observability: The Event Fails Silently
- A database connection pool exhausts at 400 req/s
- Customers see "Something went wrong" (5xx errors)
- Engineering team doesn't notice for 5+ minutes
- **Result: 120,000 failed requests × lost conversions**

### 2. With Observability: We Catch It Instantly
- Grafana alert fires at 1% error rate → engineer notified in < 30s
- Sentry shows the exact error: "too many clients" in PostgreSQL
- Engineer scales Cloud SQL connections → event continues
- **Result: < 60 seconds downtime, minimal revenue impact**

### 3. Post-Event: Data-Driven Decisions
- Grafana dashboards show exactly which endpoints were hottest
- Sentry performance traces identify slowest queries
- We know exactly where to invest optimization effort
- **Result: Every shilling of dev time goes where it matters most**

---

## Risk & Mitigation

| Risk | Mitigation |
|------|-----------|
| Prometheus/Grafana adds operational overhead | Runs as single docker-compose on existing VM; 5-minute setup |
| Sentry data privacy | `send_default_pii=False`; no customer PII sent |
| Metrics endpoint adds latency | Single counter increment per request (~0.001ms overhead) |
| Team doesn't use the tools | Dashboards pre-built; runbook for event; 15-min onboarding |

---

## Bottom Line

**For zero additional infrastructure cost**, we get:

1. **Real-time error visibility** — Sentry catches bugs as they happen
2. **Live performance dashboard** — Grafana shows latency, throughput, errors
3. **Structured debugging** — JSON logs queryable in Cloud Logging
4. **Event runbook** — exact playbook for 5xx spikes, latency, DB issues

**The only cost is 15 minutes of engineer time to set up.** The cost of NOT having this during a marketing event is unknown downtime, lost revenue, and damaged customer trust.

---

## Recommendation

**Approve now.** The implementation is already deployed in this branch. Production activation requires:
1. Creating a free Sentry account → setting `SENTRY_DSN` env var
2. Running `docker compose -f deploy/monitoring/docker-compose.monitoring.yml up -d`

Both steps take < 20 minutes combined.
