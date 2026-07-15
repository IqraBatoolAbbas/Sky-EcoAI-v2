# Sky.EcoAI

Sky.EcoAI is an **Autonomous Green Fleet Control Tower** for climate & sustainability hackathons. It plans low-cost, low-emission multi-vehicle delivery routes, detects disruptions (breakdowns, urgent orders, road blockage, low range), automatically generates recovery plans, and explains decisions through an AI Fleet Copilot.

Legacy partner features (auth, single A→B route tool, ledger, admin) remain available alongside the Control Tower.

## Auth & APIs (Control Tower)

| Need | What to use |
|------|-------------|
| Judge quick start | Login → **Continue as Demo Operator** (`POST /api/demo-login`) |
| Full account | Signup / login session cookie |
| Admin | `/admin/login` (separate admin session) |
| Fleet APIs | Require login/demo session — all `/api/fleet/*` |
| Floating help | Public `POST /api/help/chat` (RAG, read-only) |
| Optional LLM | `GEMINI_API_KEY` or `OPENAI_API_KEY` for richer grounded answers |
| Session secret | `FLASK_SECRET_KEY` env (stable default for local hackathon) |

RAG knowledge lives in `knowledge/*.md` and is retrieved with live fleet KPIs before answering.

### Extra Control Tower extras

- **Scenario presets:** Medical rush, Carbon-budget breach, EV low range (`POST /api/fleet/scenarios`)
- **Before → After KPIs** on Impact Report after recovery
- **Operator activity log** on Overview
- **Impact one-pager:** `/control-tower/impact-print` (Print / Save as PDF)
- **Voice:** mic buttons use free Web Speech API (Chrome/Edge); say “run guided demo” or “optimize fleet”
- **NL GenAI scenarios:** Event Center text → structured disruptions (`POST /api/fleet/scenario/nl`)
- **Carbon budget enforcement:** over-budget plans receive score penalties
- **Judge Mode:** GenAI impact narrative + SDG scoreboard + simulated WhatsApp/email alerts
- **Impact score:** composites deliveries protected, CO₂ avoided, and agent actions




## What's new (fleet control tower)

| Module | Responsibility |
|--------|----------------|
| `fleet_store.py` | Vehicles, orders, plans, events, decisions (`data/fleet_state.json`) |
| `fleet_optimizer.py` | Google OR-Tools multi-vehicle CVRP with Economy / Green / Service modes |
| `carbon_cost_engine.py` | Distance, operating cost (PKR), estimated CO₂e |
| `disruption_agent.py` | Breakdown, urgent order, road blockage, range warning + recovery |
| `fleet_copilot.py` | Structured tool calling + optional Gemini/OpenAI explanation |

Seeded dataset: `data/lahore_demo.json` (6 vehicles, 12 Lahore deliveries).

### Fleet API endpoints

- `GET /api/fleet/dashboard` — KPIs and alerts
- `GET/POST /api/fleet/vehicles` — list / create vehicles
- `GET/POST /api/fleet/orders` — list / create orders
- `POST /api/fleet/optimize` — generate route plans (`mode`: `all` \| `economy` \| `green` \| `service`)
- `POST /api/fleet/plans/<id>/apply` — apply selected plan
- `POST /api/fleet/events` — create disruption (`breakdown`, `urgent_order`, `road_blockage`, `range_warning`)
- `POST /api/fleet/recovery` — generate (and optionally auto-apply) recovery plans
- `GET /api/fleet/decisions` — agent decision timeline
- `POST /api/fleet/copilot` — natural-language control with tool calls
- `GET /api/fleet/impact` — impact summary
- `POST /api/fleet/reset-demo` — restore Lahore seed scenario

## Legacy SaaS features

Authentication, premium subscription simulation, admin management, support tickets, ledger analytics, and the single-route A→B workspace (`/workspace`) from the original partner build.

## Tech Stack

- Python 3 + Flask 3.0.3
- Google OR-Tools (multi-vehicle routing)
- Leaflet + OpenStreetMap (fleet map)
- JSON state store for fleet MVP (`data/fleet_state.json`)
- Optional: `GEMINI_API_KEY` or `OPENAI_API_KEY` for richer Copilot explanations

## Usage

### Setup

1. Clone the repository.
2. Create a Python virtual environment:
   ```bash
   python -m venv .venv
   .\.venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Run the App

```bash
python app.py
```

Visit:

- Control Tower: `http://127.0.0.1:5000/control-tower`
- Home: `http://127.0.0.1:5000`

### Run fleet tests

```bash
pip install pytest
pytest tests/test_fleet_flow.py -q
```

### Default Admin Credentials

- Email: `admin@sky-ecoai.local`
- Password: `ChangeMe123`

Update this admin password immediately in a production deployment.

### Notes

- Carbon values are **estimates** based on configured conversion factors.
- Keep API keys in environment variables — never commit `.env`.
- Confirm `data/` is writable before running.
- See `docs/IMPLEMENTATION_STATUS.md` for plan alignment and remaining polish items.

### Live Demo

https://sky-ecoai.vercel.app/
