# GuardianSwarm

GuardianSwarm is a hackathon-ready autonomous SOC prototype. It streams synthetic security logs, lets four AI agents collaborate in real time, explains their reasoning, persists incidents, and autonomously logs, notifies, or blocks simulated threats.

## Architecture

- **Frontend:** React + Tailwind dashboard in `frontend/`
- **Backend:** FastAPI service in `backend/`
- **Realtime:** WebSocket stream at `/ws/live`
- **Database:** MongoDB via `MONGO_URL`, with an in-memory fallback for quick demos
- **AI reasoning:** OpenAI-compatible LLM calls when `OPENAI_API_KEY` is set, with a local reasoning simulator for offline demos

## Agent Loop

GuardianSwarm runs continuously through:

1. **Observe:** live logs arrive from the sample generator
2. **Think:** agents reason over telemetry and shared incident context
3. **Act:** the swarm logs, notifies, or blocks based on risk
4. **Learn:** operator feedback updates future reasoning notes

Agents:

- **Triage Agent:** detects suspicious patterns in live logs
- **Forensics Agent:** correlates historical user, host, IP, and telemetry context
- **Decision Agent:** assigns risk and explains the decision
- **Action Agent:** executes autonomous response and records learning

## Demo Flow

Press **Simulate Attack** in the dashboard.

The backend generates an attack chain:

```text
failed login burst
successful login after password spray
new cloud access key
beacon-like DNS
encoded PowerShell
external IAM principal
large archive upload
```

The dashboard then shows:

- live log streaming
- each agent's live thinking
- incident timeline: Observe -> Think -> Act -> Learn
- risk graph escalation
- threat heatmap intensifying
- autonomous containment when risk becomes critical
- manual override and feedback learning controls

## Setup

### Quick Start

From the project root:

```bash
npm run backend
```

Open a second terminal:

```bash
npm run dev
```

Then visit:

```text
http://127.0.0.1:5173
```

If Vite says `5173` is busy, use the alternate port it prints, such as `5174`.

### 1. Start MongoDB

```bash
docker compose up -d
```

MongoDB is optional. If it is not running, the backend still works with an in-memory incident store.

### 2. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You can also run this from the root:

```bash
npm run backend
```

For real LLM reasoning, add your key to `backend/.env`:

```text
OPENAI_API_KEY=your_key_here
```

### 3. Frontend

Open a new terminal:

```bash
cd frontend
npm install
npm run dev
```

You can also run this from the root:

```bash
npm run dev
```

Visit the Vite URL, usually:

```text
http://localhost:5173
```

## API

- `GET /api/health` - backend and database status
- `GET /api/incidents` - latest persisted incidents
- `GET /api/logs` - latest live log buffer
- `GET /api/stats` - summary metrics and blocked entities
- `POST /api/attack` - force the attack simulation to start
- `POST /api/feedback` - submit learning feedback
- `POST /api/override/{incident_id}` - manual override broadcast
- `POST /api/reset` - reset in-memory simulation state
- `WS /ws/live` - live logs, agent thoughts, incident updates

## Why This Wins Demos

GuardianSwarm does not feel like a static dashboard. The system narrates its own investigation: multiple agents share context, risk rises as evidence accumulates, the UI visualizes pressure across the attack surface, and the Action Agent contains the simulated threat without waiting for a human analyst.
