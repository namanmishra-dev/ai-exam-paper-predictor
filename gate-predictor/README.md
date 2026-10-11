# GATE PYQ Analyzer & Mock Paper Generator 🚀

A production-grade web product helping Computer Science (CS) students preparing for GATE decide which topics to prioritize and attempt realistic mock papers built from official PYQ statistics and RAG-generated questions.

> **Disclaimer**: All priority scores and paper generated outputs are trend-based statistical guidance. GATE question selection is non-deterministic.

---

## Key Features

1. **Evidence-Based Topic Prioritization**: Ranks topics into `Must-Do` (~60% yield), `Should-Do` (~25%), and `Skip-If-Short` (~15%) using recency weighting ($\lambda=0.15$), linear trend extrapolation, consistency, and appearance gap analysis.
2. **Deterministic Backtesting Framework**: Walk-forward temporal evaluation proving priority rankings beat Uniform and Naive Frequency baselines across past GATE papers.
3. **Question Bank & RAG Generator**: Original GATE-style question generation using Claude API with RAG retrieval of top-k reference PYQs.
4. **5-Step Automated Verification Gate**:
   - Step 1: Independent LLM solver call without seeing answer key.
   - Step 2: Sandboxed Python numerical execution for NAT questions.
   - Step 3: Exact set equality check for MSQ option keys.
   - Step 4: Near-duplicate rejection (cosine similarity $\le 0.90$).
   - Step 5: Strict Pydantic schema validation.
5. **Deterministic Mock Paper Assembler**: Blueprint-driven knapsack solver assembling 65-question / 100-mark mock papers with attempt history deduplication.
6. **Official Scoring Engine**: Enforces exact GATE negative marking rules (1-mark MCQ: $+1 / -1/3$, 2-mark MCQ: $+2 / -2/3$, MSQ: $+marks / 0$, NAT: $+marks / 0$).
7. **FastAPI & Next.js Web Application**: Glassmorphic dark theme dashboard and interactive exam attempt environment.

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- Docker & Docker Compose (optional, for DB & Redis)

### Step 1: Clone & Environment Setup
```bash
cd gate-predictor
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install -e .
cp .env.example .env
```

### Step 2: Run Priorities Precomputation
```bash
python scripts/compute_priorities.py --subject operating_systems
```

### Step 3: Run Backtest Evaluation
```bash
python scripts/run_backtest.py --subject operating_systems
```

### Step 4: Pre-Fill Question Bank
```bash
python scripts/fill_bank.py --count-per-topic 3
```

### Step 5: Start FastAPI API Server
```bash
uvicorn app.main:app --reload --port 8000
```
- Interactive API Swagger Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/api/v1/health`

### Step 6: Start Next.js Frontend
```bash
cd frontend
npm install
npm run dev
```
- Open Web App: `http://localhost:3000`

---

## Docker Compose Deployment

Spin up all microservices (PostgreSQL+pgvector, Redis, FastAPI, Celery worker, Next.js frontend):

```bash
docker-compose up -d --build
```

Services exposed:
- **Web App**: `http://localhost:3000`
- **FastAPI API**: `http://localhost:8000`
- **Swagger Docs**: `http://localhost:8000/docs`
- **PostgreSQL**: `localhost:5432`
- **Redis**: `localhost:6379`

---

## Deployment Guide (Cloud Platforms)

### Deploying to Render / Railway
1. **Database & Cache**: Provision a PostgreSQL database with pgvector extension enabled and a Redis instance.
2. **API Web Service**: Set build command `pip install -e .` and start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4`.
3. **Background Worker**: Provision a background worker service with start command `celery -A app.workers.celery_app worker --loglevel=info`.
4. **Frontend**: Deploy `frontend/` as a Web Service or Static Site with `NEXT_PUBLIC_API_URL` pointing to your backend API URL.

### Deploying to AWS (ECS / EC2)
1. Push Docker images (`api`, `worker`, `frontend`) to AWS ECR.
2. Create an Amazon Aurora PostgreSQL (or RDS PostgreSQL with pgvector) and ElastiCache Redis cluster.
3. Deploy ECS Task Definitions behind an Application Load Balancer (ALB) with SSL/TLS certificates attached.

---

## Test Suite Execution

Run the complete suite of 85 unit and golden tests:

```bash
pytest tests/unit/ tests/golden/ -v --tb=short -m "not integration"
```

---

## GATE Copyright & Educational Compliance Notice

Previous Year Questions (PYQs) and answer keys are the intellectual property of the organizing Indian Institutes of Technology (IITs) and the GATE Committee.

- **Attribution**: All ingested official PYQ data is sourced directly from official GATE organizing institute repositories for educational and research purposes.
- **Fair Use**: Ingested PYQs are presented under fair-use educational guidance for Computer Science aspirants preparing for competitive examinations.
- **Generated Questions**: All AI-generated questions are distinctly tagged with `source="generated"` to clearly differentiate them from official PYQ records.
