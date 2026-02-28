# Deploy Affordable Gadgets Backend to Google Cloud

Single VM on **Google Compute Engine**. Two options:

1. **Terraform + Docker (recommended, no Ansible)** – one script does everything; firewall in Terraform (no GCP Console).
2. **Terraform + Ansible** – VM + config via Ansible (optional).

**Firewall (22, 80, 443) is defined in Terraform** – you do not need to create rules in the GCP Console.

## Prerequisites

- **Google Cloud** account and project; [gcloud CLI](https://cloud.google.com/sdk/docs/install) installed and authenticated (`gcloud auth login`, `gcloud auth application-default login`).
- **Terraform** >= 1.0: [install](https://developer.hashicorp.com/terraform/downloads).
- **Docker is not required on your machine** – the script copies a tarball to the VM and runs `docker compose` there (Docker is installed on the VM if needed).
- For Ansible path only: **Ansible** >= 2.12 and SSH key in GCP.

---

## Option 1: Terraform + Docker (no Ansible, no GCP UI)

From the **backend repo root**, with a `.env` that has at least `SECRET_KEY` and your other app vars:

```bash
./deploy/deploy-gcp.sh
```

This does everything from code:

1. **Terraform apply** – creates the VM and **firewall rule** (ports 22, 80, 443).
2. Copies the backend tarball and a generated `.env` (with `ALLOWED_HOSTS` = VM IP) to the VM.
3. SSHs into the VM, installs Docker if needed, runs `docker compose up -d --build`.

No GCP Console, no Ansible. App: `http://<VM_IP>:8000`.

- **Skip Terraform** (VM already exists): `SKIP_TERRAFORM=1 ./deploy/deploy-gcp.sh`
- **Using ngrok for HTTPS:** Deploy overwrites the VM `.env` and sets `ALLOWED_HOSTS` to the VM IP only. If you use ngrok, run `./deploy/ngrok-on-vm.sh` **after** each deploy so the ngrok host is added to `ALLOWED_HOSTS` and CORS. Otherwise the backend returns **400 Bad Request** on login/API calls from the admin/frontend.
- **Remote user** (if not `ubuntu`): `REMOTE_USER=youruser ./deploy/deploy-gcp.sh`

### HTTPS URL for Vercel (no domain): ngrok on the VM

To use the GCP backend from your HTTPS Vercel frontends without Mixed Content, run ngrok on the VM to get an HTTPS URL:

```bash
./deploy/ngrok-on-vm.sh
```

The script installs ngrok on the VM, starts a tunnel to port 8000, and prints the HTTPS URL. It also updates the VM `.env` (ALLOWED_HOSTS and CORS) and restarts the app. Add the printed URL to your Vercel env (e.g. `REACT_APP_API_BASE_URL=<url>/api/inventory` for admin, `NEXT_PUBLIC_API_URL=<url>` for frontend), then redeploy the frontends.

Optional: set `NGROK_AUTH_TOKEN` (from [ngrok dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)) so the URL is stable and there’s no interstitial page:

```bash
NGROK_AUTH_TOKEN=your_token ./deploy/ngrok-on-vm.sh
```

---

## Option 2: Terraform + Ansible

### 1. Create the VM with Terraform

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: set project_id (e.g. gmail-486411), region, zone.
terraform init
terraform plan
terraform apply
```

Note the **external IP** (e.g. from `terraform output external_ip`). You will use it for Ansible and for `ALLOWED_HOSTS`.

Optional: set `enable_startup_script = true` in `terraform.tfvars` so the VM has Python 3 installed on first boot (Ansible can then run without waiting for apt).

## 2. Configure Ansible

Set the backend VM IP in the inventory and variables.

**Option A – One-off run with Terraform output**

```bash
export TF_OUT=$(terraform -chdir=deploy/terraform output -raw external_ip 2>/dev/null)
ansible-playbook -i "${TF_OUT}," deploy/ansible/playbook.yml --extra-vars "ansible_user=ubuntu"
```

**Option B – Use inventory file**

1. Edit `deploy/ansible/inventory/hosts.yml`: replace `EXTERNAL_IP` with the VM’s external IP (or use the Terraform output above).
2. Edit `deploy/ansible/group_vars/backend.yml`:
   - `db_password`: strong password for the PostgreSQL app user.
   - `secret_key`: Django secret (e.g. `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`).
   - `allowed_hosts`: include the VM’s external IP and/or your domain (e.g. `1.2.3.4,api.example.com`).
   - `cors_allowed_origins`, `frontend_base_url`, `csrf_trusted_origins` for your frontend and API domain.
   - Optionally set Cloudinary and Pesapal variables (or use `ansible-vault` for secrets).

Then run:

```bash
cd /path/to/affordable-gadgets-backend   # repo root (parent of deploy/)
ansible-playbook -i deploy/ansible/inventory/hosts.yml deploy/ansible/playbook.yml
```

If your SSH user is not `ubuntu`, pass it:

```bash
ansible-playbook -i deploy/ansible/inventory/hosts.yml deploy/ansible/playbook.yml -e ansible_user=YOUR_USER
```

## 3. What Ansible does

- **postgres**: Installs PostgreSQL, creates database and user, allows local password auth.
- **django**: Creates app user, syncs code from your repo (from the machine running Ansible), creates venv, installs dependencies, deploys `.env` from template, runs **migrate only** (no `makemigrations` on the server), runs `collectstatic`, optional `seed_delivery_rates` and `create_superuser_from_env`, installs Gunicorn systemd service.
- **nginx**: Installs Nginx, configures reverse proxy to Gunicorn (127.0.0.1:8000), serves `/static/` (and optionally `/media/`).

Gunicorn runs with `--timeout 120` and 2 workers as in your existing deployment docs.

## 4. Re-deploy (code or config changes)

From repo root:

```bash
# Update inventory if IP changed
ansible-playbook -i deploy/ansible/inventory/hosts.yml deploy/ansible/playbook.yml
```

Only the **django** role syncs code and runs migrate/collectstatic; re-run the full playbook or use `--tags django` to update only the app.

## 5. Secrets

- Do **not** commit `terraform.tfvars` or `group_vars/backend.yml` if they contain real secrets.
- Use **Ansible Vault** for production:

  ```bash
  ansible-vault create deploy/ansible/group_vars/backend_vault.yml
  # Put db_password, secret_key, cloudinary_*, pesapal_* there
  ansible-playbook ... --ask-vault-pass
  ```

- Or pass secrets on the CLI: `-e db_password=... -e secret_key=...` (avoid storing in shell history).

## 6. Migrations

- Migrations are **only applied** on the server (`migrate --noinput`). New migrations must be created locally (`makemigrations`), committed, then re-run the playbook so the synced code and migrate step pick them up.

## 7. Structure

```
deploy/
├── README.md           # this file
├── terraform/
│   ├── main.tf         # GCE instance, firewall, optional static IP
│   ├── variables.tf
│   ├── outputs.tf      # external_ip, instance_name for Ansible
│   ├── terraform.tfvars.example
│   └── startup.sh.tpl  # optional bootstrap (install Python)
└── ansible/
    ├── playbook.yml
    ├── ansible.cfg
    ├── inventory/hosts.yml
    ├── group_vars/
    │   ├── all.yml
    │   └── backend.yml   # db_*, secret_key, allowed_hosts, etc.
    └── roles/
        ├── postgres/
        ├── django/       # sync code, venv, .env, migrate, collectstatic, gunicorn
        └── nginx/
```

## 8. Troubleshooting

- **SSH**: Use `ssh ubuntu@EXTERNAL_IP` (or your key/user). If you use gcloud, `gcloud compute ssh INSTANCE_NAME --zone=ZONE` works.
- **PostgreSQL 14 path**: If your image uses a different Postgres version, set `pg_hba_path` in the postgres role or in `group_vars` (role currently assumes `/etc/postgresql/14/main/pg_hba.conf`).
- **App not responding**: Check `sudo systemctl status gunicorn-affordable-gadgets` and `sudo journalctl -u gunicorn-affordable-gadgets -f`. Ensure `ALLOWED_HOSTS` includes the VM IP or domain.

### Frontend shows "Error loading products / Failed to fetch"

1. **Vercel env for this deployment**  
   The frontend uses `NEXT_PUBLIC_API_BASE_URL` at **build time**. Set it in Vercel → Project → Settings → Environment Variables for **Production** and **Preview** (or "All"). If you only set it for Production, branch/preview URLs (e.g. `*-git-*-*.vercel.app`) will have no API URL and will fall back to `http://localhost:8000` → "Failed to fetch". After changing env vars, **redeploy** (trigger a new deployment).

2. **Backend reachable**  
   From your machine, check the backend (or ngrok URL) responds:
   ```bash
   curl -s -o /dev/null -w "%{http_code}" https://YOUR_NGROK_URL/health/
   ```
   You should get `200`. If it fails, ngrok may be down or the URL changed; run `./deploy/ngrok-on-vm.sh` again and update `NEXT_PUBLIC_API_BASE_URL` in Vercel, then redeploy.

3. **Which URL to test**  
   Use the **production** URL (e.g. `https://affordable-gadgets-frontend.vercel.app`) to confirm; preview URLs only work if the same env vars are set for Preview.
