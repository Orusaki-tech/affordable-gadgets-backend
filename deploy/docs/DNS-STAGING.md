# Staging DNS (Cloudflare)

Point these records to Terraform outputs `shop_lb_ip`, `admin_lb_ip`; API via tunnel to `api_lb_ip`.

| Host | Type | Target |
|------|------|--------|
| staging.affordable-gadgetske.com | A | shop_lb_ip |
| admin-staging.affordable-gadgetske.com | A | admin_lb_ip |
| api-staging.affordable-gadgetske.com | CNAME | tunnel / existing api hostname |

Set GitHub vars: `STAGING_API_URL`, Vercel optional until cutover.
