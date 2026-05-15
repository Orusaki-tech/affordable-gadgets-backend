# Cloudflare Tunnel → API load balancer

On the platform stack, **do not** point the tunnel at a single VM. Point it at the **internal HTTP load balancer** fronting the API MIG.

## Get the origin address

```bash
cd deploy/terraform
terraform output -raw api_lb_ip
# Example: 34.x.x.x
```

## Cloudflare Zero Trust

1. **Networks → Tunnels** — create or reuse a tunnel; copy the token into `deploy/ansible/secrets/staging.vault.yml` as `cloudflare_tunnel_token`.
2. Deploy tunnel VM config:
   ```bash
   ansible-playbook -i deploy/ansible/inventory/staging \
     deploy/ansible/playbooks/tunnel.yml -e env_name=staging --ask-vault-pass
   ```
3. **Public Hostname** (Zero Trust → your tunnel → Public Hostname):
   - Add or edit **`api-staging.affordable-gadgetske.com`** (staging) and/or **`api.affordable-gadgetske.com`** (production cutover).
   - **Service type:** HTTP
   - **URL:** `http://<api_lb_ip>` (port **80** — global LB forwards to instance port 8000)
   - Not `http://<api_lb_ip>:8000` (nothing listens on 8000 on the LB IP).
   - Not HTTPS to the LB (TLS terminates at Cloudflare).
   - **Remove** legacy origins like `http://web:8000` (old single-VM Docker service name) — that causes **502** from Cloudflare.

## Health checks

Cloudflare should hit `/health/` through the tunnel. Confirm:

```bash
curl -sf "https://api-staging.affordable-gadgetske.com/health/"
```

## Production cutover

Same pattern for `api.affordable-gadgetske.com` using production `api_lb_ip`. Update Django `ALLOWED_HOSTS` / Pesapal IPN URLs in vault before switching DNS.

## Shop / admin

Shop and admin use **A records** to `shop_lb_ip` and `admin_lb_ip` (see [DNS-STAGING.md](DNS-STAGING.md)), not the tunnel.
