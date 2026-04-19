# How .env is used (local vs production VM)

Your repo `.env` is the **source** for production, but the deploy script **overwrites** some values on the VM. That can cause confusion.

## What deploy-gcp.sh does with .env

When you run `./deploy/deploy-gcp.sh`:

1. It reads your **local** `.env`.
2. It **strips** these keys: `ALLOWED_HOSTS`, `DATABASE_URL`, `DJANGO_SETTINGS_MODULE`, `DJANGO_ENV`, `REDIS_URL`.
3. It **writes** a new env file for the VM with:
   - Everything else from your .env (CORS, SECRET_KEY, Cloudinary, Pesapal, etc.).
   - **ALLOWED_HOSTS** = `{VM_IP},localhost,127.0.0.1` plus optional extras: either `DEPLOY_EXTRA_ALLOWED_HOSTS` (comma-separated) before deploy, or—if ngrok is already running on the VM—the hostname read from ngrok’s local API (`127.0.0.1:4040`). No stale hardcoded ngrok domain is baked in.
   - **DATABASE_URL** = `postgresql://affordable:affordable@postgres:5432/affordable_gadgets` (Docker Postgres on the VM).

So on the **VM**, production does **not** use your .env’s `ALLOWED_HOSTS` or `DATABASE_URL`. It uses the VM IP for hosts (and any detected/extra hostnames) and the **container Postgres** for the DB.

## Does your .env cause conflicts?

| Variable | In your .env | What production (VM) actually uses | Conflict? |
|----------|----------------|-------------------------------------|-----------|
| **ALLOWED_HOSTS** | localhost, 127.0.0.1, ngrok host | Replaced by deploy: VM IP + localhost + optional ngrok host (detected on VM or `DEPLOY_EXTRA_ALLOWED_HOSTS`). If ngrok was not running during deploy, run `./deploy/ngrok-on-vm.sh` after starting the tunnel. | No conflict in the file. |
| **DATABASE_URL** | (empty); you have DB_HOST=Render | Replaced by deploy with Docker postgres on VM. So **production VM uses the local Postgres container**, not Render. | Only a conflict if you intended production to use Render Postgres. If you want VM to use Render, the deploy script would need to stop overriding DATABASE_URL and use your DB_* or DATABASE_URL. |
| **CORS_ALLOWED_ORIGINS** | Both Vercel admin and frontend | Copied as-is to the VM. | No conflict. |
| **FRONTEND_BASE_URL** | Often localhost in dev | **deploy-gcp.sh** sets `https://www.affordable-gadgetske.com` if missing, empty, or localhost (override with `DEPLOY_FRONTEND_BASE_URL` or a valid HTTPS URL in `.env`). Required for Django to boot in production. |
| **PESAPAL_IPN_URL** | `https://affordable-gadgets-backend.onrender.com/...` | Copied as-is. Pesapal will call **Render**, not your GCP/ngrok backend. | **Yes.** If the live backend is GCP + ngrok, IPN should point at that backend (e.g. `https://your-ngrok-host.ngrok-free.dev/api/inventory/pesapal/ipn/` or a stable production URL). |
| **SECURE_SSL_REDIRECT** | true | Copied. Behind ngrok, requests to Django are often HTTP. Redirect to HTTPS is usually fine (redirects to ngrok HTTPS). | Optional: if you see redirect loops or odd behavior, try `SECURE_SSL_REDIRECT=false` for the VM. |

## Summary

- Your `.env` **is** what gets used as the base for production: CORS, SECRET_KEY, Cloudinary, Pesapal, etc. are copied to the VM.
- **ALLOWED_HOSTS** and **DATABASE_URL** on the VM are **not** taken from your .env; they are set by the deploy script (and ngrok script for ALLOWED_HOSTS).
- **Fix for login (ngrok):** Prefer starting ngrok on the VM **before** `./deploy/deploy-gcp.sh` so the deploy script can detect the current tunnel hostname. If the tunnel URL changes after deploy, run `./deploy/ngrok-on-vm.sh` (updates `ALLOWED_HOSTS` and recreates the web container) and update Vercel’s API base URL + redeploy the frontends. For a URL that never changes, use an ngrok reserved domain or a real DNS name.
- **Fix for Pesapal IPN:** If production is GCP + ngrok, set `PESAPAL_IPN_URL` in your `.env` to your current HTTPS API base + path. Redeploy so the VM gets the new value. Prefer a stable production URL instead of a random ngrok hostname.
