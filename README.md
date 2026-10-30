# TasteOS

**The Cultural Intelligence Layer for AI Agents.**

TasteOS is a reusable cultural-intelligence API backed by [Qloo](https://docs.qloo.com/) Taste AI. The flagship demo, **Group Concierge**, helps people with different tastes negotiate a shared outing — with inspectable evidence and trade-offs, not a black-box chatbot.

> Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/)

## Try it (no login)

- **Demo:** [https://tasteos.netlify.app](https://tasteos.netlify.app)
- **API (live Qloo):** [https://tasteos-api-845068580921.us-central1.run.app](https://tasteos-api-845068580921.us-central1.run.app)
- **OpenAPI:** [https://tasteos-api-845068580921.us-central1.run.app/docs](https://tasteos-api-845068580921.us-central1.run.app/docs)

1. Open the demo and choose three demo profiles (or create anonymous ones).
2. Request a Group Concierge plan for a city (for example New York) and inspect affinity, trade-offs, and the pipeline.
3. Open **Developers** in the app (or `/docs` on the API) to see how an agent would call the same endpoints over HTTP.

## Problem

Agents can plan steps, but they are culturally blind. Groups stall when tastes conflict. Generic LLM advice averages preferences into bland suggestions and cannot show *why* an option fits each person.

## Solution

TasteOS Core exposes profiles, search, recommendations, and provenance over HTTP. Group Concierge orchestrates a modular pipeline (resolve → retrieve → constrain → negotiate → compose → explain) so judges can see Qloo-retrieved evidence versus TasteOS application ranking (`tasteos_negotiation_v1`).

## How TasteOS uses Qloo

Without Qloo there are **no taste-based recommendations**. Location alone can return places; taste signals come from Qloo entity IDs resolved from favorites and passed into Insights.

| Stage | What happens | Where Qloo runs |
| --- | --- | --- |
| 1. Resolve | Load demo or stored profiles; normalize favorites, preferences, exclusions | — |
| 2. Retrieve | Build cultural candidates for the target domain (usually places) | **Search** resolves names / demo favorites to entity UUIDs; **Insights** ranks candidates from those signals plus optional location |
| 3. Constrain | Drop hard exclusions, prior rejections, and budget filters | — |
| 4. Negotiate | Deterministic group ranking (`tasteos_negotiation_v1`) using evidence + optional `qloo_affinity` | Affinity is copied only when Insights returns it |
| 5. Compose | Build a proposed itinerary and alternatives | — |
| 6. Explain | Trade-offs, selection rationale, booking disclaimer | — |

At runtime:

- **Qloo Search** (`GET /search`) — edit-preferences and live retrieval resolve free-text or demo favorites to real entity IDs.
- **Qloo Insights** (`GET /v2/insights`) — recommendations use `signal.interests.entities` (UUIDs only) and optional location filters.

Local **demo** mode (`TASTEOS_MODE=demo`) uses a labeled sample dataset (`tasteos_demo_dataset`) so development works without quota. The **public** Cloud Run API runs **live** Qloo. Demo data is never presented as live Qloo.

## TasteOS as an agentic tool

TasteOS is a **cultural-intelligence tool** that AI agents call over HTTP. An agent (or any client) can create/load profiles, resolve entities via search, and ask Group Concierge for a negotiated plan — then reject a pick and regenerate — without embedding Qloo keys in the agent or browser.

Interactive contract: [OpenAPI `/docs`](https://tasteos-api-845068580921.us-central1.run.app/docs). Full route notes: [docs/API.md](docs/API.md).

### Example agent call — `POST /api/v1/concierge/plan`

```bash
curl -sS "https://tasteos-api-845068580921.us-central1.run.app/api/v1/concierge/plan" \
  -H "Content-Type: application/json" \
  -d '{
    "profile_ids": [
      "demo-profile-maya",
      "demo-profile-jordan",
      "demo-profile-sam"
    ],
    "target_domain": "urn:entity:place",
    "location_query": "New York",
    "experience": "evening_out",
    "alternatives_count": 3,
    "take": 6
  }'
```

Example response shape (fields abbreviated):

```json
{
  "id": "…",
  "mode": "live",
  "primary": {
    "entity_id": "…",
    "name": "…",
    "source": "qloo",
    "qloo_affinity": 0.72,
    "app_rank_score": 0.81,
    "participant_matches": []
  },
  "alternatives": [],
  "itinerary": [],
  "tradeoffs": "…",
  "pipeline": [
    { "stage": "candidate_retrieve", "source": "qloo_insights", "signal_entity_count": 3 }
  ],
  "limitations": []
}
```

## Features

- Anonymous taste profiles (nickname only) + demo profiles + reset/delete
- Entity search and recommendations via verified Qloo client (live) or labeled demo data
- Group Concierge: shared plan, itinerary (proposed only), alternatives, reject/regenerate
- Transparent negotiation scores (`app_rank_score`) separate from `qloo_affinity`
- OpenAPI at `/docs`, CLI `check-qloo`, CORS allowlist, rate limits, redacted errors

## Architecture

```mermaid
flowchart LR
  Web[Next.js Group Concierge] --> API[FastAPI TasteOS]
  API -->|live| Qloo[Qloo hackathon API]
  API -->|demo| Demo[Labeled demo dataset]
  API --> DB[(PostgreSQL)]
```

Modules: Taste Profile Resolver → Cultural Candidate Retriever → Constraint Evaluator → Negotiation Engine → Plan Composer → Explanation Generator. Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Technology stack

| Layer | Stack |
| --- | --- |
| Frontend | Next.js App Router, TypeScript, Tailwind, shadcn/ui |
| Backend | Python 3.11+, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Cultural AI | Qloo Search + Insights |
| Hosting | Netlify (frontend) & Google Cloud Run (API, live Qloo) |

## Repository layout

```text
apps/web     Next.js UI
apps/api     FastAPI Core + Concierge
docs/        Architecture, API contracts, deployment, security
scripts/     Helpers (e.g. bundle secret scan)
```

## Local installation

**Prerequisites:** Node 20+, Python 3.11+, npm. Optional: Docker, Qloo hackathon API key.

### 1. Clone and environment file

**Windows (PowerShell)**

```powershell
cd path\to\TasteOS
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

**Linux / macOS**

```bash
cd path/to/TasteOS
[ -f .env ] || cp .env.example .env
```

### 2. Python virtualenv and API deps

**Windows (PowerShell)**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -e "apps/api[dev]"
```

**Linux / macOS**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e "apps/api[dev]"
```

### 3. Run API and web

**Windows (PowerShell)** — Terminal A (API):

```powershell
cd apps\api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Windows (PowerShell)** — Terminal B (web):

```powershell
cd apps\web
npm install
npm run dev
```

**Linux / macOS** — Terminal A (API):

```bash
cd apps/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Linux / macOS** — Terminal B (web):

```bash
cd apps/web
npm install
npm run dev
```

- Web: http://localhost:3000
- API health: http://localhost:8000/health
- OpenAPI: http://localhost:8000/docs

### Environment variables

Copy [`.env.example`](.env.example) to `.env`. Use **placeholder values only** in docs and tickets — never commit real secrets.

| Variable | Where | Example / placeholder | Notes |
| --- | --- | --- | --- |
| `TASTEOS_MODE` | API | `demo` or `live` | Public Cloud Run uses `live` |
| `QLOO_API_KEY` | API only | `your-qloo-hackathon-key` | Required for live; never `NEXT_PUBLIC_*` |
| `QLOO_BASE_URL` | API | `https://hackathon.api.qloo.com` | Hackathon host |
| `DATABASE_URL` | API | `postgresql+psycopg://tasteos:CHANGE_ME@localhost:5432/tasteos` | `postgresql://` is auto-normalized |
| `FRONTEND_URL` | API | `http://localhost:3000` | Exact web origin for CORS |
| `CORS_ORIGINS` | API | `https://example.netlify.app` | Optional comma-separated extras |
| `NEXT_PUBLIC_API_BASE_URL` | Web | `http://localhost:8000` | Public API base URL only (no secrets) |
| `TASTEOS_API_KEY` | API | _(empty locally)_ | Optional write protection via `X-TasteOS-Key` |

### CLI

```bash
cd apps/api
python -m app.cli mode
python -m app.cli check-qloo   # live Search→Insights; never prints the key
```

Exit codes for `check-qloo`: `0` ok · `1` upstream/auth failure · `2` key not configured.

## API documentation

- Production OpenAPI: [https://tasteos-api-845068580921.us-central1.run.app/docs](https://tasteos-api-845068580921.us-central1.run.app/docs)
- Contracts: [docs/API.md](docs/API.md)

Core routes include `/api/v1/profiles*`, `/api/v1/search`, `/api/v1/recommendations`, `/api/v1/concierge/plan`, reject/regenerate.

## Tests

**Windows (PowerShell)**

```powershell
cd apps\api
pytest -q --ignore=tests/test_qloo_integration.py

# Optional live Qloo integration
# $env:TASTEOS_RUN_LIVE_QLOO='1'; pytest -m integration -q tests/test_qloo_integration.py

cd ..\web
npm run lint; npm run typecheck; npm run build
npx playwright test   # needs API + web running
```

**Linux / macOS**

```bash
cd apps/api
pytest -q --ignore=tests/test_qloo_integration.py

# Optional live Qloo integration
# TASTEOS_RUN_LIVE_QLOO=1 pytest -m integration -q tests/test_qloo_integration.py

cd ../web
npm run lint && npm run typecheck && npm run build
npx playwright test   # needs API + web running
```

## Deployment

| Role | Target | URL |
| --- | --- | --- |
| Frontend | Netlify | [https://tasteos.netlify.app](https://tasteos.netlify.app) |
| Backend API | Google Cloud Run (**live** Qloo) | [https://tasteos-api-845068580921.us-central1.run.app](https://tasteos-api-845068580921.us-central1.run.app) |
| OpenAPI | Cloud Run | [https://tasteos-api-845068580921.us-central1.run.app/docs](https://tasteos-api-845068580921.us-central1.run.app/docs) |

Detailed guide (Cloud Run primary; optional Docker Compose self-host): [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Security and privacy

- Secrets server-side; logging redacts credential patterns
- CORS allowlist; rate limits; Pydantic validation; ~1 MB body cap
- Anonymous nicknames only; profile delete supported
- See [docs/SECURITY.md](docs/SECURITY.md)

## Known limitations

- Group consensus is TasteOS-ranked — Qloo does not guarantee agreement.
- Itineraries are **proposals**, not bookings.
- Favorites without a resolvable Qloo entity ID are skipped in live Insights (noted in `limitations`).
- Public GitHub/GitLab URL must be published by the entrant for full Devpost eligibility.

## License

[MIT](LICENSE) — see the [LICENSE](LICENSE) file in the repository root.
