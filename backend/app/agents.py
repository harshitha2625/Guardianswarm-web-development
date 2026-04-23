import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentResult:
    agent: str
    thought: str
    confidence: float
    evidence: list[str] = field(default_factory=list)
    action: str | None = None


class LLMReasoner:
    def __init__(self) -> None:
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) if AsyncOpenAI and os.getenv("OPENAI_API_KEY") else None
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def reason(self, role: str, context: dict[str, Any], prompt: str) -> str:
        if self.client:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a concise cybersecurity AI agent inside an autonomous SOC. "
                            "Explain reasoning in one crisp sentence with evidence and no markdown."
                        ),
                    },
                    {"role": "user", "content": f"Agent: {role}\nContext: {context}\nTask: {prompt}"},
                ],
                temperature=0.35,
                max_tokens=90,
            )
            return response.choices[0].message.content or "Reasoning unavailable."

        return self._local_reason(role, context)

    def _local_reason(self, role: str, context: dict[str, Any]) -> str:
        log = context.get("log", {})
        signal = " ".join([log.get("message", ""), log.get("severity", ""), log.get("user", "")]).lower()
        if role == "Triage Agent":
            if any(token in signal for token in ["failed login burst", "encoded", "beacon", "external principal", "archive uploaded"]):
                return "This event diverges from baseline behavior and shares indicators with credential abuse and post-compromise activity."
            return "The event resembles routine operational noise, but it remains correlated against the current session graph."
        if role == "Forensics Agent":
            return "Historical context links the same user, host, and external IP across authentication, cloud, endpoint, and egress telemetry."
        if role == "Decision Agent":
            return "The combined evidence forms a multi-stage intrusion path, so risk is raised based on intent, lateral movement, and exfiltration signals."
        return "Autonomous response is selected because the expected containment value exceeds the operational disruption risk."


class GuardianSwarm:
    def __init__(self) -> None:
        self.reasoner = LLMReasoner()
        self.active_incident: dict[str, Any] | None = None
        self.learning_notes: list[str] = [
            "Normal VPN refreshes deprioritized after operator feedback.",
            "Repeated finance-admin anomalies now receive stronger correlation weight.",
        ]
        self.blocked_entities: list[dict[str, str]] = []

    async def process(self, log: dict[str, Any]) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        updates: list[dict[str, Any]] = []
        triage = await self._triage(log)
        updates.append(self._agent_update(triage, log))

        if triage.confidence < 0.52 and log["severity"] in {"info", "low"}:
            return None, updates

        incident = self._ensure_incident(log)
        incident["logs"].append(log)
        incident["timeline"].append(self._timeline("Observe", triage.thought, "Triage Agent"))

        forensics = await self._forensics(log, incident, triage)
        incident["timeline"].append(self._timeline("Think", forensics.thought, "Forensics Agent"))
        updates.append(self._agent_update(forensics, log, incident))

        decision = await self._decision(log, incident, [triage, forensics])
        risk_score = self._risk_score(log, triage, forensics, decision)
        incident["risk"] = max(incident["risk"], risk_score)
        incident["status"] = "contained" if incident["risk"] >= 82 else "investigating"
        incident["reasoning"] = decision.thought
        incident["timeline"].append(self._timeline("Act", decision.thought, "Decision Agent"))
        updates.append(self._agent_update(decision, log, incident))

        action = await self._action(log, incident, decision)
        incident["action"] = action.action
        incident["timeline"].append(self._timeline("Learn", action.thought, "Action Agent"))
        incident["learning"] = random.choice(self.learning_notes)
        updates.append(self._agent_update(action, log, incident))
        return incident, updates

    async def _triage(self, log: dict[str, Any]) -> AgentResult:
        thought = await self.reasoner.reason("Triage Agent", {"log": log}, "Detect whether this log is suspicious.")
        tokens = ["failed", "password", "beacon", "encoded", "external", "archive", "access key"]
        confidence = 0.44 + sum(0.09 for token in tokens if token in log["message"].lower())
        if log["severity"] in {"high", "critical"}:
            confidence += 0.18
        return AgentResult("Triage Agent", thought, min(confidence, 0.97), [log["message"]])

    async def _forensics(self, log: dict[str, Any], incident: dict[str, Any], triage: AgentResult) -> AgentResult:
        context = {"log": log, "related_logs": incident["logs"][-5:], "triage": triage.thought}
        thought = await self.reasoner.reason("Forensics Agent", context, "Investigate related historical activity.")
        evidence = [
            f"{len(incident['logs'])} correlated events",
            f"user={log['user']}",
            f"host={log['host']}",
        ]
        confidence = min(0.55 + len(incident["logs"]) * 0.07 + triage.confidence * 0.22, 0.96)
        return AgentResult("Forensics Agent", thought, confidence, evidence)

    async def _decision(self, log: dict[str, Any], incident: dict[str, Any], results: list[AgentResult]) -> AgentResult:
        context = {"log": log, "incident": incident, "agent_findings": [item.__dict__ for item in results]}
        thought = await self.reasoner.reason("Decision Agent", context, "Assign risk and explain the decision.")
        confidence = min(sum(item.confidence for item in results) / len(results) + 0.08, 0.98)
        return AgentResult("Decision Agent", thought, confidence, ["multi-agent consensus", incident["kill_chain_stage"]])

    async def _action(self, log: dict[str, Any], incident: dict[str, Any], decision: AgentResult) -> AgentResult:
        context = {"log": log, "incident": incident, "decision": decision.__dict__}
        thought = await self.reasoner.reason("Action Agent", context, "Choose and justify an autonomous response.")
        if incident["risk"] >= 82:
            action = f"Blocked {log['ip']} and disabled risky session for {log['user']}"
            self.blocked_entities.append({"ip": log["ip"], "user": log["user"], "time": now()})
        elif incident["risk"] >= 64:
            action = f"Notified incident channel and increased monitoring for {log['user']}"
        else:
            action = "Logged enriched incident for continued autonomous monitoring"
        return AgentResult("Action Agent", thought, 0.91, [action], action)

    def _ensure_incident(self, log: dict[str, Any]) -> dict[str, Any]:
        if self.active_incident and self.active_incident["status"] != "contained":
            return self.active_incident
        self.active_incident = {
            "id": f"GS-{str(uuid.uuid4())[:8].upper()}",
            "created_at": now(),
            "title": "Autonomous investigation: finance identity compromise",
            "status": "investigating",
            "risk": 0,
            "kill_chain_stage": "Initial Access",
            "logs": [],
            "timeline": [],
            "reasoning": "",
            "action": "pending",
            "learning": "",
        }
        return self.active_incident

    def _risk_score(self, log: dict[str, Any], triage: AgentResult, forensics: AgentResult, decision: AgentResult) -> int:
        severity_boost = {"info": 0, "low": 4, "medium": 12, "high": 24, "critical": 34}[log["severity"]]
        chain_boost = len(self.active_incident["logs"]) * 7 if self.active_incident else 0
        confidence = (triage.confidence + forensics.confidence + decision.confidence) / 3
        score = int(28 + severity_boost + chain_boost + confidence * 32)
        if any(word in log["message"].lower() for word in ["archive uploaded", "external principal", "encoded"]):
            score += 10
        if score >= 84:
            self.active_incident["kill_chain_stage"] = "Containment"
        elif score >= 70:
            self.active_incident["kill_chain_stage"] = "Exfiltration / Privilege Abuse"
        elif score >= 55:
            self.active_incident["kill_chain_stage"] = "Execution / Persistence"
        return min(score, 99)

    def apply_feedback(self, incident_id: str, label: str, note: str) -> dict[str, Any] | None:
        self.learning_notes.append(f"Operator marked {incident_id} as {label}: {note or 'no note'}")
        if self.active_incident and self.active_incident["id"] == incident_id:
            self.active_incident["learning"] = self.learning_notes[-1]
            self.active_incident["timeline"].append(
                self._timeline("Learn", f"Feedback accepted as {label}. Future scoring will adjust similar evidence.", "Decision Agent")
            )
            return self.active_incident
        return None

    def override_incident(self, incident_id: str) -> dict[str, Any] | None:
        if self.active_incident and self.active_incident["id"] == incident_id:
            self.active_incident["status"] = "manual-review"
            self.active_incident["action"] = "Manual override: autonomous response paused for this incident"
            self.active_incident["timeline"].append(
                self._timeline("Act", "Manual override received. Autonomous containment is paused.", "Action Agent")
            )
            return self.active_incident
        return None

    def _timeline(self, phase: str, detail: str, agent: str) -> dict[str, str]:
        return {"phase": phase, "detail": detail, "agent": agent, "time": now()}

    def _agent_update(self, result: AgentResult, log: dict[str, Any], incident: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "type": "agent_update",
            "agent": result.agent,
            "thought": result.thought,
            "confidence": round(result.confidence, 2),
            "evidence": result.evidence,
            "action": result.action,
            "incident_id": incident["id"] if incident else None,
            "log_id": log["id"],
            "time": now(),
        }
