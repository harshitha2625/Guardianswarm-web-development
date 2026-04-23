import os
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient


class IncidentStore:
    def __init__(self) -> None:
        self.mongo_url = "mongodb://localhost:27017"
        self.db_name = "guardianswarm"
        self.client: AsyncIOMotorClient | None = None
        self.collection = None
        self.memory: list[dict[str, Any]] = []
        self.connected = False

    async def connect(self) -> None:
        self.mongo_url = os.getenv("MONGO_URL", self.mongo_url)
        self.db_name = os.getenv("MONGO_DB", self.db_name)
        try:
            self.client = AsyncIOMotorClient(self.mongo_url, serverSelectionTimeoutMS=900)
            await self.client.admin.command("ping")
            self.collection = self.client[self.db_name]["incidents"]
            await self.collection.create_index("id", unique=True)
            await self.collection.create_index("updated_at")
            self.connected = True
        except Exception:
            self.connected = False

    async def upsert_incident(self, incident: dict[str, Any]) -> None:
        incident["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.connected and self.collection is not None:
            await self.collection.update_one(
                {"id": incident["id"]},
                {"$set": incident},
                upsert=True,
            )
            return

        for index, existing in enumerate(self.memory):
            if existing["id"] == incident["id"]:
                self.memory[index] = incident
                return
        self.memory.append(incident)

    async def list_incidents(self, limit: int = 30) -> list[dict[str, Any]]:
        if self.connected and self.collection is not None:
            cursor = self.collection.find({}, {"_id": 0}).sort("updated_at", -1).limit(limit)
            return [doc async for doc in cursor]
        return sorted(self.memory, key=lambda item: item.get("updated_at", ""), reverse=True)[:limit]


store = IncidentStore()
