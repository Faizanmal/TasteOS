# Deployment — TasteOS

**Production architecture**

* **Frontend:** Next.js on **Netlify** — [https://tasteos.netlify.app](https://tasteos.netlify.app) ([`netlify.toml`](../netlify.toml))
* **Backend API:** FastAPI on **Google Cloud Run** in **live** Qloo mode — [https://tasteos-api-845068580921.us-central1.run.app](https://tasteos-api-845068580921.us-central1.run.app)
* **OpenAPI:** [https://tasteos-api-845068580921.us-central1.run.app/docs](https://tasteos-api-845068580921.us-central1.run.app/docs)
* **Optional self-host:** Docker Compose ([`docker-compose.yml`](../docker-compose.yml)) on any VM or laptop

---

## Pre-flight (verified locally)

From the repository root:

**Windows (PowerShell)**

```powershell
cd path\to\TasteOS\apps\api
..\..\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_qloo_integration.py

cd ..\web
npm run lint
npm run typecheck
npm run build

cd ..\..
.\.venv\Scripts\python.exe scripts\scan_bundle_secrets.py
```

**Linux / macOS**

```bash
cd path/to/TasteOS/apps/api
../../.venv/bin/python -m pytest -q --ignore=tests/test_qloo_integration.py

cd ../web
npm run lint
npm run typecheck
npm run build

cd ../..
.venv/bin/python scripts/scan_bundle_secrets.py
```

---

## 1. Public Git repository

```bash
cd path/to/TasteOS
gh auth login
gh repo create TasteOS --public --source=. --remote=origin --push
```

Verify that `.env`, `apps/api/.env`, and `apps/web/.env.local` are untracked.

---

## 2. Backend (Google Cloud Run — production)

Production TasteOS API runs on Cloud Run with:

* `TASTEOS_MODE=live`
* `QLOO_API_KEY` supplied via Secret Manager / Cloud Run secrets (never in the browser or `NEXT_PUBLIC_*`)
* `DATABASE_URL` pointing at managed or companion PostgreSQL
* `FRONTEND_URL` / `CORS_ORIGINS` including `https://tasteos.netlify.app`

Build and deploy the container image from `apps/api` (Dockerfile at repo root or `apps/api` as configured in your project). Example shape (replace project/region/image as needed):

```bash
# Build & push (example)
gcloud builds submit --tag REGION-docker.pkg.dev/PROJECT/REPO/tasteos-api:latest

# Deploy (wire secrets; do not pass real keys on the CLI in shared logs)
gcloud run deploy tasteos-api \
  --image REGION-docker.pkg.dev/PROJECT/REPO/tasteos-api:latest \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "TASTEOS_MODE=live,QLOO_BASE_URL=https://hackathon.api.qloo.com,FRONTEND_URL=https://tasteos.netlify.app" \
  --set-secrets "QLOO_API_KEY=QLOO_API_KEY:latest,DATABASE_URL=DATABASE_URL:latest"
```

Confirm:

```bash
curl -fsS "https://tasteos-api-845068580921.us-central1.run.app/health"
curl -fsS "https://tasteos-api-845068580921.us-central1.run.app/api/v1/mode"
```

Expect `mode` to report **live** with `qloo_key_configured: true` (boolean only — never the key).

### Environment variables (placeholders only)

| Variable | Placeholder | Notes |
| --- | --- | --- |
| `TASTEOS_MODE` | `live` | Production Cloud Run |
| `QLOO_API_KEY` | `your-qloo-hackathon-key` | Secret Manager |
| `QLOO_BASE_URL` | `https://hackathon.api.qloo.com` | Hackathon host |
| `DATABASE_URL` | `postgresql+psycopg://USER:PASSWORD@HOST:5432/tasteos` | Server-side only |
| `FRONTEND_URL` | `https://tasteos.netlify.app` | CORS primary origin |
| `CORS_ORIGINS` | `https://tasteos.netlify.app` | Optional extras |

---

## 3. Optional self-host (Docker Compose)

Use when you want a local or VM replica. This is **not** the public production path.

```bash
git clone <YOUR_REPO_URL> TasteOS
cd TasteOS

cat << 'EOF' > .env
APP_ENV=production
TASTEOS_MODE=live
QLOO_BASE_URL=https://hackathon.api.qloo.com
QLOO_API_KEY=your-qloo-hackathon-key
FRONTEND_URL=https://YOUR-SITE-NAME.netlify.app
CORS_ORIGINS=https://YOUR-SITE-NAME.netlify.app,http://localhost:3000
POSTGRES_USER=tasteos
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_DB=tasteos
DATABASE_URL=postgresql+psycopg://tasteos:CHANGE_ME@db:5432/tasteos
EOF

docker compose up -d --build
docker compose exec api alembic upgrade head
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/api/v1/mode
```

> [!IMPORTANT]
> Netlify is HTTPS. Browsers block HTTPS pages calling plain HTTP APIs. Expose the Compose API over HTTPS (Cloudflare Tunnel, Caddy, or a reverse proxy) before pointing Netlify at it.

---

## 4. Frontend (Netlify)

[`netlify.toml`](../netlify.toml) configures Next.js App Router and `@netlify/plugin-nextjs`.

### Connect repository

1. Log in to [app.netlify.com](https://app.netlify.com).
2. **Add new site** → **Import an existing project**.
3. Select the `TasteOS` repository.

### Build settings

* **Base directory:** `apps/web`
* **Build command:** `npm run build`
* **Publish directory:** `.next`

### Environment variable

| Variable | Value |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | `https://tasteos-api-845068580921.us-central1.run.app` |

### Deploy

1. Deploy the site.
2. Confirm the Netlify URL (`https://tasteos.netlify.app`).
3. Ensure Cloud Run `FRONTEND_URL` / `CORS_ORIGINS` include that exact origin.

### Verified live deployments

| Service | Host | Live URL | Status |
| --- | --- | --- | --- |
| **Frontend UI** | Netlify | https://tasteos.netlify.app | Live |
| **Backend API** | GCP Cloud Run (live Qloo) | https://tasteos-api-845068580921.us-central1.run.app | Live |
| **OpenAPI Docs** | GCP Cloud Run | https://tasteos-api-845068580921.us-central1.run.app/docs | Live |

---

## 5. Production verification checklist

- [x] Frontend loads over HTTPS (`https://tasteos.netlify.app`)
- [x] `GET {API}/health` → 200 `status=ok`
- [x] `GET {API}/api/v1/mode` → `live`, no secrets in body
- [x] Browser Network tab: frontend calls API without CORS or mixed content errors
- [ ] Concierge journey: select 3 profiles → build plan → reject pick → primary updates
- [ ] PostgreSQL tables verified (`taste_profiles`, `recommendations`)

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Browser blocks API request (`Mixed Content`) | Frontend is HTTPS; API must be HTTPS (Cloud Run already is). |
| CORS errors in browser | `FRONTEND_URL` / `CORS_ORIGINS` on the API must match the exact Netlify origin. |
| API 503 `database_unavailable` | Check `DATABASE_URL` and DB connectivity from Cloud Run. |
| Alembic migration failure (Compose) | `docker compose exec api alembic upgrade head` |
| 401 from Qloo | Confirm `QLOO_BASE_URL` is `https://hackathon.api.qloo.com` and `QLOO_API_KEY` is set on the service. |
| `signal_entity_count` is 0 | Favorites need real Qloo UUIDs (Search) or resolvable demo seeds; invalid IDs are skipped with a limitation note. |

---

## Security reminders

- Never put `QLOO_API_KEY` or `DATABASE_URL` in `NEXT_PUBLIC_*` or client bundles.
- Store production secrets in Secret Manager / the host secret store — not in git.
- See [SECURITY.md](SECURITY.md).
