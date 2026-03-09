# Vercel + ngrok env checklist

Use this after running `./deploy/ngrok-on-vm.sh` to ensure Admin and Frontend are configured correctly.

## 1. Vercel – Admin (affordable-gadgets-admin)

In **Vercel → affordable-gadgets-admin → Settings → Environment Variables**:

| Name | Value | Environments |
|------|--------|--------------|
| `REACT_APP_API_BASE_URL` | `https://YOUR-NGROK-HOST.ngrok-free.dev/api/inventory` | Production, Preview (optional) |

- **No trailing slash.** The app appends paths like `/units/`, `/products/`, etc.
- Example: `https://unreversed-nonadmissible-kandis.ngrok-free.dev/api/inventory`
- Redeploy the Admin after changing (env is baked in at build time).

## 2. Vercel – Frontend (affordable-gadgets-frontend, customer site)

In **Vercel → affordable-gadgets-frontend → Settings → Environment Variables**:

| Name | Value | Environments |
|------|--------|--------------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://YOUR-NGROK-HOST.ngrok-free.dev` | Production, Preview (optional) |

- **Backend root URL only** (no `/api/inventory`). The app appends `/api/v1/public/...`, `/api/inventory/...`, etc.
- Example: `https://unreversed-nonadmissible-kandis.ngrok-free.dev`
- Redeploy the Frontend after changing.

## 3. Backend VM (ALLOWED_HOSTS + CORS)

`./deploy/ngrok-on-vm.sh` updates the VM `.env` to:

- Add the **ngrok host** to `ALLOWED_HOSTS` (e.g. `unreversed-nonadmissible-kandis.ngrok-free.dev`)
- Append to `CORS_ALLOWED_ORIGINS` (script may add the ngrok URL; CORS must list **client origins**)

Ensure `CORS_ALLOWED_ORIGINS` in the VM `.env` includes your **Vercel app origins** (where the browser runs), for example:

- `https://affordable-gadgets-admin.vercel.app` (Admin)
- `https://your-customer-site.vercel.app` (Frontend, if it talks to the same backend)

Not the ngrok URL—that is the backend; CORS lists who is allowed to call it.

It then restarts the web container so Django picks up the new settings. If you change the ngrok URL or add a new frontend origin, run the script again or edit the VM `.env` and restart:

```bash
# On VM (or via deploy script)
cd /home/ubuntu/affordable-gadgets-backend
sudo docker-compose up -d --force-recreate web
```

## 4. Quick verify

- **Admin:** Log in at `https://affordable-gadgets-admin.vercel.app`. If you see “Server returned an HTML page…”, check `REACT_APP_API_BASE_URL` and that the backend ALLOWED_HOSTS/CORS include the ngrok host and Vercel origin.
- **Frontend:** Open the customer site; products/checkout should load. If API calls fail, check `NEXT_PUBLIC_API_BASE_URL` and CORS.

## 5. Troubleshooting: "Server returned an HTML page instead of JSON"

This usually means the backend rejected the request (e.g. Host not in ALLOWED_HOSTS), ngrok returned its interstitial page, or the VM/backend is not running.

**VM must be running.** If you ran `./deploy/vm-control.sh stop`, the VM (and ngrok, Django) is off. Start it, then run ngrok again:

```bash
./deploy/vm-control.sh start
# Wait ~1 minute for the VM to boot, then:
NGROK_AUTH_TOKEN=your_token ./deploy/ngrok-on-vm.sh
```

Use the URL the script prints. If it changed, set **Vercel** `REACT_APP_API_BASE_URL` to that URL (e.g. `https://NEW-HOST.ngrok-free.dev/api/inventory`) and redeploy the Admin.

**On the backend VM:**

1. **ALLOWED_HOSTS** must include the **ngrok host** (the host in your API URL). After every deploy, run:
   ```bash
   ./deploy/ngrok-on-vm.sh
   ```
   so the VM `.env` gets the ngrok host in ALLOWED_HOSTS and the app is restarted.

2. **CORS_ALLOWED_ORIGINS** in the VM `.env` must include the **Vercel admin origin**:
   ```bash
   CORS_ALLOWED_ORIGINS=...,https://affordable-gadgets-admin.vercel.app
   ```
   (CORS lists *client* origins; the ngrok URL is the backend.)

**On Vercel (Admin):**

3. Set **REACT_APP_API_BASE_URL** to your backend base + `/api/inventory`, e.g.  
   `https://YOUR-NGROK-HOST.ngrok-free.dev/api/inventory`  
   (no trailing slash). Redeploy the Admin so the new value is baked in.

## Reference (current ngrok URL)

After running `./deploy/ngrok-on-vm.sh`, the script prints the exact values. For a stable URL, set `NGROK_AUTH_TOKEN` and run:

```bash
NGROK_AUTH_TOKEN=your_token ./deploy/ngrok-on-vm.sh
```

Then set in Vercel:

- Admin: `REACT_APP_API_BASE_URL=<printed-ngrok-url>/api/inventory`
- Frontend: `NEXT_PUBLIC_API_BASE_URL=<printed-ngrok-url>`
