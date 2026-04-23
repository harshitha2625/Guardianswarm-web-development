import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from pydantic import BaseModel

from .agents import GuardianSwarm
from .db import store
from .simulator import LogGenerator


load_dotenv()
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


class Feedback(BaseModel):
    incident_id: str
    label: str
    note: str = ""


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for connection in self.connections:
            try:
                await connection.send_json(message)
            except Exception:
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


manager = ConnectionManager()
generator = LogGenerator()
swarm = GuardianSwarm()
feedback_notes: list[dict[str, str]] = []
recent_logs: list[dict[str, Any]] = []
simulation_task: asyncio.Task | None = None


async def simulation_loop() -> None:
    while True:
        log = generator.next_log()
        recent_logs.insert(0, log)
        del recent_logs[80:]
        await manager.broadcast({"type": "log", "payload": log})
        incident, updates = await swarm.process(log)
        for update in updates:
            await manager.broadcast(update)
            await asyncio.sleep(0.22)
        if incident:
            await store.upsert_incident(incident)
            await manager.broadcast({"type": "incident", "payload": incident})
        await asyncio.sleep(1.05)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global simulation_task
    await store.connect()
    simulation_task = asyncio.create_task(simulation_loop())
    yield
    if simulation_task:
        simulation_task.cancel()
        try:
            await simulation_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="GuardianSwarm API", version="1.0.0", lifespan=lifespan)
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "online",
        "db": "mongodb" if store.connected else "memory-fallback",
        "websocket_clients": len(manager.connections),
        "llm": "openai" if swarm.reasoner.client else "local-simulator",
    }


@app.get("/api/incidents")
async def incidents() -> list[dict[str, Any]]:
    return await store.list_incidents()


@app.get("/api/logs")
async def logs() -> list[dict[str, Any]]:
    return recent_logs[:50]


@app.get("/api/stats")
async def stats() -> dict[str, Any]:
    incidents_list = await store.list_incidents()
    contained = [incident for incident in incidents_list if incident.get("status") == "contained"]
    active = swarm.active_incident
    return {
        "logs_processed": len(recent_logs),
        "incidents": len(incidents_list),
        "contained": len(contained),
        "active_incident": active["id"] if active else None,
        "current_risk": active["risk"] if active else 0,
        "blocked_entities": swarm.blocked_entities[-10:],
    }


@app.post("/api/attack")
async def trigger_attack() -> dict[str, str]:
    generator.force_attack()
    return {"status": "attack simulation queued"}


@app.post("/api/feedback")
async def feedback(item: Feedback) -> dict[str, str]:
    feedback_notes.append(item.model_dump())
    incident = swarm.apply_feedback(item.incident_id, item.label, item.note)
    if incident:
        await store.upsert_incident(incident)
        await manager.broadcast({"type": "incident", "payload": incident})
    await manager.broadcast({"type": "feedback", "payload": item.model_dump()})
    return {"status": "learning signal accepted"}


@app.post("/api/override/{incident_id}")
async def override(incident_id: str) -> dict[str, str]:
    incident = swarm.override_incident(incident_id)
    if incident:
        await store.upsert_incident(incident)
        await manager.broadcast({"type": "incident", "payload": incident})
    await manager.broadcast(
        {
            "type": "override",
            "payload": {
                "incident_id": incident_id,
                "message": "Manual override received. Agent autonomy reduced for this incident.",
            },
        }
    )
    return {"status": "override broadcast"}


@app.post("/api/reset")
async def reset() -> dict[str, str]:
    recent_logs.clear()
    swarm.active_incident = None
    await manager.broadcast({"type": "reset", "payload": {"message": "Simulation state reset"}})
    return {"status": "reset complete"}


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_json(
            {
                "type": "snapshot",
                "payload": {
                    "message": "GuardianSwarm live channel connected",
                    "logs": recent_logs[:24],
                    "incidents": await store.list_incidents(),
                    "health": await health(),
                },
            }
        )
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")


@app.get("/")
async def dashboard():
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend build missing. Run `npm run frontend:build` from the project root."}


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Frontend build missing. Run `npm run frontend:build` from the project root."}
