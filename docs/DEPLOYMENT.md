# Deployment — TasteOS

**Target Architecture:**
* **Frontend:** Next.js deployed on **Netlify** (via [`netlify.toml`](../netlify.toml))
* **Backend & Database:** FastAPI & PostgreSQL running in Docker on a **GCP Compute Engine VM** (via [`docker-compose.yml`](../docker-compose.yml))

---

## Pre-flight (verified locally)

```powershell
# Backend unit tests
cd E:\Hackathons\devpost\Qloo\apps\api
..\..\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_qloo_integration.py

# Frontend lint, typecheck, build
cd ..\web
npm run lint
npm run typecheck
npm run build
```

Verify client bundle contains zero secrets:
```powershell
cd E:\Hackathons\devpost\Qloo
.\.venv\Scripts\python.exe scripts\scan_bundle_secrets.py
```

---

## 1. Public Git Repository

```powershell
cd E:\Hackathons\devpost\Qloo
gh auth login
gh repo create TasteOS --public --source=. --remote=origin --push
```

Verify that `.env`, `apps/api/.env`, and `apps/web/.env.local` are untracked.

---

## 2. Backend & Database (GCP Compute Engine VM with Docker)

The backend runs containerized with Docker Compose using [`docker-compose.yml`](../docker-compose.yml) (`api` FastAPI + `db` PostgreSQL 16).

### Step 2.1: Open GCP Firewall Rule
Allow inbound traffic on port 8000 (and 80/443 if using a reverse proxy):
```powershell
gcloud compute firewall-rules create allow-tasteos-backend `
  --direction=INGRESS `
  --priority=1000 `
  --network=default `
  --action=ALLOW `
  --rules=tcp:8000,tcp:80,tcp:443 `
  --source-ranges=0.0.0.0/0 `
  --target-tags=http-server,https-server
```

### Step 2.2: Create or Select Compute Engine VM
```powershell
gcloud compute instances create tasteos-backend-vm `
  --zone=us-central1-a `
  --machine-type=e2-medium `
  --image-family=debian-12 `
  --image-project=debian-cloud `
  --tags=http-server,https-server
```

### Step 2.3: SSH into the VM & Install Docker
```powershell
gcloud compute ssh tasteos-backend-vm --zone=us-central1-a
```
Inside the VM shell:
```bash
sudo apt update && sudo apt install -y git curl docker.io docker-compose-v2
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2.4: Clone Repo & Configure Environment
```bash
git clone <YOUR_REPO_URL> TasteOS
cd TasteOS

cat << 'EOF' > .env
APP_ENV=production
TASTEOS_MODE=demo
QLOO_BASE_URL=https://hackathon.api.qloo.com
QLOO_API_KEY=
FRONTEND_URL=https://YOUR-SITE-NAME.netlify.app
CORS_ORIGINS=https://YOUR-SITE-NAME.netlify.app,http://localhost:3000
POSTGRES_USER=tasteos
POSTGRES_PASSWORD=tasteos_secure_password
POSTGRES_DB=tasteos
EOF
```

### Step 2.5: Launch Stack & Run Migrations
```bash
# Launch PostgreSQL + FastAPI
docker compose up -d --build

# Run Alembic migrations against PostgreSQL
docker compose exec api alembic upgrade head

# Healthcheck
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/api/v1/mode
```

> [!IMPORTANT]
> **Mixed Content Notice:** Netlify serves frontends over HTTPS (`https://*.netlify.app`). Modern browsers block requests from HTTPS sites to unencrypted HTTP backends (`http://<VM_IP>:8000`). To provide HTTPS on the VM:
> * **Option A (Instant & Free):** Run Cloudflare Tunnel inside Docker on the VM:
>   ```bash
>   docker run -d --restart unless-stopped --network host cloudflare/cloudflared:latest tunnel --url http://localhost:8000
>   ```
>   Check `docker logs <container-id>` for your generated `https://xxxx.trycloudflare.com` URL.
> * **Option B:** Map a domain to your VM external IP and configure Caddy/Nginx for automatic Let's Encrypt SSL.

---

## 3. Frontend (Netlify)

The project includes [`netlify.toml`](../netlify.toml) configured for Next.js App Router and `@netlify/plugin-nextjs`.

### Step 3.1: Connect Repository
1. Log in to [app.netlify.com](https://app.netlify.com).
2. Click **Add new site** $\to$ **Import an existing project**.
3. Authorize GitHub/GitLab and select the `TasteOS` repository.

### Step 3.2: Confirm Build Settings
Netlify will auto-detect [`netlify.toml`](../netlify.toml):
* **Base directory:** `apps/web`
* **Build command:** `npm run build`
* **Publish directory:** `.next`

### Step 3.3: Set Environment Variable
Under **Site configuration** $\to$ **Environment variables**, add:
* `NEXT_PUBLIC_API_BASE_URL`: Your backend HTTPS URL (e.g. your Cloudflare tunnel HTTPS URL or custom domain HTTPS URL).

### Step 3.4: Deploy
1. Click **Deploy Site**.
2. Note your assigned Netlify URL (e.g. `https://tasteos-concierge.netlify.app`).
3. Update `FRONTEND_URL` in `.env` on your GCP VM to match this origin, then reload the API:
   ```bash
   docker compose restart api
   ```

---

## 4. Production Verification Checklist

- [ ] Frontend loads over HTTPS (`https://*.netlify.app`)  
- [ ] `GET {API}/health` $\to$ 200 `status=ok`  
- [ ] `GET {API}/api/v1/mode` $\to$ no secrets in body  
- [ ] Browser Network tab: frontend calls API without CORS or mixed content errors  
- [ ] Demo Concierge journey: select 3 profiles $\to$ build plan $\to$ reject pick $\to$ primary updates  
- [ ] PostgreSQL tables verified (`taste_profiles`, `recommendations`)  

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Browser blocks API request (`Mixed Content`) | Frontend is HTTPS, but API is HTTP. Expose port 8000 with Cloudflare tunnel or Caddy SSL. |
| CORS errors in browser | `FRONTEND_URL` in VM `.env` must match the exact Netlify domain (`https://….netlify.app`). |
| API 503 `database_unavailable` | Ensure `db` container is healthy (`docker compose ps`), check `DATABASE_URL`. |
| Alembic migration failure | Run `docker compose exec api alembic upgrade head`. |
| 401 from Qloo | Confirm `QLOO_BASE_URL` is `https://hackathon.api.qloo.com` and `QLOO_API_KEY` is set. |

---

## Security Reminders

- Never put `QLOO_API_KEY` or `DATABASE_URL` in `NEXT_PUBLIC_*` or client bundles.
- Keep `.env` files server-side only on the VM.
- See [SECURITY.md](SECURITY.md).
