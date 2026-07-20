# Sky.EcoAI

Sky.EcoAI is an **Autonomous Green Fleet Control Tower** for climate & sustainability hackathons. It plans low-cost, low-emission multi-vehicle delivery routes, detects disruptions (breakdowns, urgent orders, road blockage, low range), automatically generates recovery plans, and explains decisions through an AI Fleet Copilot.

Legacy partner features (auth, single A→B route tool, ledger, admin) remain available alongside the Control Tower.

## 🏆 Evaluation Criteria

### 🏆 Innovation & Creativity
Sky.EcoAI introduces a novel approach to sustainable logistics by combining **multi-objective route optimization** with **autonomous disruption recovery**. The system features three distinct optimization modes (Economy, Green, Service) that balance cost, emissions, and service level priorities. The **AI Fleet Copilot** demonstrates innovation in human-AI collaboration through structured tool calling and RAG-grounded explanations, enabling natural language fleet control. The **natural language scenario generation** transforms unstructured event descriptions into structured disruption simulations, showcasing creative GenAI integration.

### 🏆 Problem Relevance & Impact
The project addresses the critical **climate challenge of reducing transportation emissions** while maintaining operational efficiency. With logistics contributing significantly to global CO₂ emissions, Sky.EcoAI provides immediate impact through:
- **Carbon budget enforcement** with real-time monitoring
- **Multi-modal fleet optimization** supporting petrol, hybrid, and electric vehicles
- **Disruption resilience** ensuring service continuity during breakdowns, road blockages, and urgent deliveries
- **Quantifiable sustainability metrics** including CO₂ avoidance calculations against all-petrol baselines
The solution directly supports **UN SDG 11 (Sustainable Cities)** and **SDG 13 (Climate Action)** with measurable environmental benefits.

### 🏆 Technical Implementation
The system demonstrates sophisticated technical architecture:
- **Google OR-Tools CVRP solver** with custom cost coefficients for multi-objective optimization
- **Real-time disruption detection** and autonomous recovery planning
- **RAG-powered knowledge retrieval** combining static documentation with live fleet state
- **Structured tool calling** in the Fleet Copilot for reliable AI agent behavior
- **Carbon cost engine** with Haversine distance calculations and emission factor modeling
- **Flask-based REST API** with comprehensive fleet management endpoints
- **Leaflet + OpenStreetMap integration** for interactive fleet visualization
- **Optional LLM integration** (Gemini/OpenAI) for enhanced natural language understanding

### 🏆 User Experience & Design
Sky.EcoAI delivers an intuitive, professional interface:
- **Control Tower dashboard** with real-time KPIs, alerts, and fleet visualization
- **Interactive map** showing vehicle routes, disruption zones, and order locations
- **Voice command support** via Web Speech API for hands-free operation
- **Guided demo mode** for seamless judge presentations
- **Impact one-pager** with print/PDF export for reporting
- **Natural language interface** through the AI Fleet Copilot chat
- **Before/After KPI comparisons** on impact reports
- **Mobile-responsive design** with modern UI components

### 🏆 Completeness & Functionality
The project delivers a fully functional MVP with:
- **Complete fleet lifecycle management**: vehicle creation, order management, route planning
- **Three optimization modes** with comparable scoring and ranking
- **Four disruption types**: breakdown, urgent order, road blockage, range warning
- **Autonomous recovery** with multi-plan generation and recommendation
- **Decision logging** and activity tracking for audit trails
- **Carbon budget management** with enforcement and penalty scoring
- **Scenario presets** for quick demonstration (medical rush, carbon breach, EV low range)
- **Natural language scenario parsing** for complex disruption sequences
- **Impact tracking** with CO₂ avoidance, delivery protection, and agent action metrics
- **Authentication system** with demo operator fast-path
- **Admin dashboard** for user and ticket management

### 🏆 Presentation & Demonstration
Sky.EcoAI excels in presentation readiness:
- **Live demo deployment** at https://sky-eco-ai-v2.vercel.app/
- **Guided demo flow** with automated scenario execution
- **Judge mode** with GenAI impact narratives and SDG scoreboard
- **Simulated communication alerts** (WhatsApp/email) for realistic disruption scenarios
- **Impact print view** for professional reporting
- **Comprehensive API documentation** with example endpoints
- **Knowledge base** in `knowledge/` directory for RAG grounding
- **Demo video guide** documentation for consistent presentations

## 🏗️ System Architecture
graph TD
    %% Styling Configuration
    classDef controlTower fill:#1b263b,stroke:#e0e1dd,stroke-width:2px,color:#fff,font-weight:bold;
    classDef coreModule fill:#415a77,stroke:#e0e1dd,stroke-width:1px,color:#fff;
    classDef subLayer fill:#778da9,stroke:#e0e1dd,stroke-width:1px,color:#fff,font-weight:bold;
    classDef engine fill:#e0e1dd,stroke:#1b263b,stroke-width:2px,color:#1b263b,font-weight:bold;

    %% Control Tower Main Container
    subgraph SkyEcoAI [Sky.EcoAI Control Tower]
        
        %% Top Core Inputs/Endpoints
        A[Flask API<br>app.py]
        B[Fleet Store<br>JSON State]
        C[RAG Store<br>Knowledge Base]
        
        %% Middle Management Layer
        subgraph FML [Fleet Management Layer]
            D[Optimizer<br>OR-Tools]
            E[Disruption Agent<br>Recovery Engine]
            F[AI Fleet Copilot<br>NLP & Tool Calling]
        end
        
        %% Bottom Computation Engine
        G[Carbon Cost Engine<br>Distance, Emissions & Cost Calculations]
        
    end

    %% Data Flow Connections
    A --> FML
    B --> FML
    C --> FML
    
    D --> G
    E --> G
    F --> G

    %% Applying Styles
    class SkyEcoAI controlTower;
    class A,B,C coreModule;
    class FML subLayer;
    class G engine;
### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     Sky.EcoAI Control Tower                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Flask API  │  │  Fleet Store │  │  RAG Store   │          │
│  │   (app.py)   │  │ (JSON State) │  │ (Knowledge)  │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│  ┌──────▼─────────────────▼─────────────────▼───────┐          │
│  │              Fleet Management Layer              │          │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐  │          │
│  │  │ Optimizer  │ │Disruption  │ │  Copilot   │  │          │
│  │  │ (OR-Tools) │ │  Agent     │ │  (AI/NLP)  │  │          │
│  │  └────────────┘ └────────────┘ └────────────┘  │          │
│  └──────────────────────────────────────────────────┘          │
│         │                 │                 │                   │
│  ┌──────▼─────────────────▼─────────────────▼───────┐          │
│  │              Carbon Cost Engine                   │          │
│  │        (Distance, Emissions, Cost Calc)          │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow Architecture

```
User Request → Flask API → Authentication → Fleet Store
                                            ↓
                                    Fleet Optimizer
                                            ↓
                                    Carbon Cost Engine
                                            ↓
                                    Route Plans (Economy/Green/Service)
                                            ↓
                                    Disruption Detection
                                            ↓
                                    Recovery Planning
                                            ↓
                                    AI Copilot Explanation
                                            ↓
                                    Response + RAG Grounding
```

### Module Responsibilities

| Module | File | Responsibility |
|--------|------|----------------|
| **Fleet Store** | `fleet_store.py` | Vehicles, orders, plans, events, decisions state management (`data/fleet_state.json`) |
| **Fleet Optimizer** | `fleet_optimizer.py` | Google OR-Tools multi-vehicle CVRP with Economy/Green/Service modes |
| **Carbon Cost Engine** | `carbon_cost_engine.py` | Distance calculation, operating cost (PKR), estimated CO₂e computations |
| **Disruption Agent** | `disruption_agent.py` | Breakdown, urgent order, road blockage, range warning simulation + recovery planning |
| **Fleet Copilot** | `fleet_copilot.py` | Structured tool calling + optional Gemini/OpenAI explanation with RAG grounding |
| **RAG Store** | `rag_store.py` | Knowledge base retrieval with live fleet KPI integration |
| **GenAI Services** | `genai_services.py` | Natural language scenario parsing and operational alert generation |

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

### Extra Control Tower Features

- **Scenario presets:** Medical rush, Carbon-budget breach, EV low range (`POST /api/fleet/scenarios`)
- **Before → After KPIs** on Impact Report after recovery
- **Operator activity log** on Overview
- **Impact one-pager:** `/control-tower/impact-print` (Print / Save as PDF)
- **Voice:** mic buttons use free Web Speech API (Chrome/Edge); say “run guided demo” or “optimize fleet”
- **NL GenAI scenarios:** Event Center text → structured disruptions (`POST /api/fleet/scenario/nl`)
- **Carbon budget enforcement:** over-budget plans receive score penalties
- **Judge Mode:** GenAI impact narrative + SDG scoreboard + simulated WhatsApp/email alerts
- **Impact score:** composites deliveries protected, CO₂ avoided, and agent actions

## 🔄 Operational Flow

### Normal Fleet Operations

1. **Initialization**: System loads with Lahore demo dataset (6 vehicles, 12 deliveries)
2. **Dashboard View**: Real-time KPIs show fleet status, pending orders, and carbon budget
3. **Route Optimization**: Operator triggers optimization → System generates 3 plans (Economy, Green, Service)
4. **Plan Selection**: Plans ranked by comparison score → Operator selects recommended plan
5. **Plan Application**: Selected plan applied → Vehicles assigned routes → KPIs updated
6. **Execution Monitoring**: Real-time tracking of deliveries, emissions, and costs

### Disruption Recovery Flow

1. **Disruption Detection**: System detects or operator simulates disruption (breakdown, urgent order, road blockage, range warning)
2. **Impact Assessment**: Affected orders identified → At-risk deliveries flagged → Alert generated
3. **Recovery Planning**: Disruption Agent generates new route plans → Service mode prioritized for at-risk orders
4. **Plan Comparison**: Recovery plans ranked → Before/After KPIs calculated → Recommendation provided
5. **Operator Approval**: Operator reviews recovery plan → Confirms or modifies
6. **Recovery Execution**: New plan applied → Vehicles rerouted → Affected orders protected
7. **Impact Logging**: Decision recorded → Activity updated → Impact metrics calculated

### AI Copilot Interaction Flow

1. **Natural Language Input**: Operator types or speaks command
2. **Intent Recognition**: Copilot parses intent → Maps to appropriate tool
3. **Tool Execution**: Structured tool call executed → Fleet state updated
4. **Response Generation**: Result formatted → RAG grounding added → Explanation provided
5. **Confirmation Flow**: For mutating actions → Operator confirmation required → Action executed
6. **Learning Loop**: Decision logged → Activity tracked → Knowledge base updated

## 📊 Dataset & Configuration

Seeded dataset: `data/lahore_demo.json` (6 vehicles, 12 Lahore deliveries)

### Vehicle Types Supported
- **Petrol**: 192g CO₂/km emission factor, PKR 15/km operating cost
- **Hybrid**: 108g CO₂/km emission factor, PKR 12/km operating cost  
- **Electric**: 48g CO₂/km emission factor, PKR 8/km operating cost

### Optimization Modes
- **Economy Mode**: Minimizes operating cost (weight: cost 1.0, emissions 0.1, distance 0.3)
- **Green Mode**: Minimizes CO₂ emissions (weight: cost 0.2, emissions 1.0, distance 0.3)
- **Service Mode**: Prioritizes delivery completion (weight: cost 0.3, emissions 0.2, lateness 1.0)

## 🔌 Fleet API Endpoints

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
- `POST /api/fleet/scenarios` — execute preset scenarios
- `POST /api/fleet/scenario/nl` — natural language scenario generation
- `GET /api/fleet/impact/narrative` — GenAI impact narrative

## 🏛️ Legacy SaaS Features

Authentication, premium subscription simulation, admin management, support tickets, ledger analytics, and the single-route A→B workspace (`/workspace`) from the original partner build.

## 🛠️ Tech Stack

### Core Technologies
- **Python 3** + **Flask 3.0.3** - Web framework and API server
- **Google OR-Tools** - Multi-vehicle routing optimization (CVRP solver)
- **Leaflet + OpenStreetMap** - Interactive fleet visualization
- **JSON state store** - Fleet state persistence (`data/fleet_state.json`)

### AI & ML Integration
- **RAG (Retrieval-Augmented Generation)** - Knowledge base integration with live fleet data
- **Optional LLM Support** - `GEMINI_API_KEY` or `OPENAI_API_KEY` for enhanced Copilot explanations
- **Natural Language Processing** - Intent recognition and scenario parsing
- **Structured Tool Calling** - Reliable AI agent behavior with function calling

### Frontend Technologies
- **HTML5/CSS3/JavaScript** - Modern responsive interface
- **Web Speech API** - Voice command support (Chrome/Edge)
- **Leaflet.js** - Interactive mapping
- **Fetch API** - Asynchronous API communication

### Data Processing
- **Haversine Distance Calculation** - Accurate distance computations
- **Carbon Emission Modeling** - Multi-factor emission calculations
- **Cost Optimization Algorithms** - Multi-objective route scoring

## 🚀 Usage

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

### Run the Application

```bash
python app.py
```

Visit:
- **Control Tower**: `http://127.0.0.1:5000/control-tower`
- **Home**: `http://127.0.0.1:5000`

### Run Tests

```bash
pip install pytest
pytest -q
```

### Default Admin Credentials

- Email: `admin@sky-ecoai.local`
- Password: `ChangeMe123`

Update this admin password immediately in a production deployment.

### Notes

- Carbon values are **estimates** based on configured conversion factors.
- “CO₂ avoided” uses an explicit all-petrol fleet counterfactual over the same planned distance; recovery Before → After remains a separate operational delta.
- Keep API keys in environment variables — never commit `.env`.
- Confirm `data/` is writable before running.
- Set `FLASK_SECRET_KEY` and `FLASK_ENV=production` in production. Use `SKY_OPTIMIZER_SECONDS` to increase OR-Tools search time for larger fleets.
- See `docs/DEMO_VIDEO_GUIDE.md` for the recommended demo flow and narration.

### Live Demo

https://sky-eco-ai-v2.vercel.app/

## 📚 Project Structure

```
Sky-EcoAI-v2-main/
├── app.py                      # Main Flask application & API routes
├── fleet_store.py              # Fleet state management
├── fleet_optimizer.py          # OR-Tools route optimization
├── carbon_cost_engine.py       # Emissions & cost calculations
├── disruption_agent.py         # Disruption simulation & recovery
├── fleet_copilot.py           # AI copilot with tool calling
├── rag_store.py                # RAG knowledge base
├── genai_services.py           # GenAI utilities
├── auth_store.py               # User authentication
├── admin_store.py              # Admin management
├── support_store.py            # Support ticket system
├── ledger_store.py             # User ledger data
├── route_agent.py              # Single-route optimization
├── actor_util.py               # Actor tracking utilities
├── requirements.txt            # Python dependencies
├── data/
│   ├── lahore_demo.json        # Demo dataset
│   ├── fleet_state.json        # Fleet state persistence
│   ├── users.json              # User accounts
│   ├── admin.json              # Admin accounts
│   ├── tickets.json            # Support tickets
│   └── ledger.json             # User ledger data
├── knowledge/
│   ├── faq_help.md             # FAQ knowledge base
│   ├── judging_climate.md      # Climate judging criteria
│   ├── operator_guide.md       # Operator guide
│   └── recovery_playbook.md    # Recovery procedures
├── templates/                  # HTML templates
├── static/                     # CSS, JS, images
└── tests/                      # Test suite
```

## 🌱 Environmental Impact

Sky.EcoAI directly contributes to climate action by:
- **Reducing fleet emissions** through optimized routing
- **Promoting electric vehicle adoption** with cost-benefit analysis
- **Enabling carbon budget management** for sustainability goals
- **Providing quantifiable metrics** for environmental reporting
- **Supporting UN SDGs** 11 (Sustainable Cities) and 13 (Climate Action)
