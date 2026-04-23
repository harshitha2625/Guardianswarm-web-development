import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const defaultApiHost = `${window.location.protocol}//${window.location.hostname}:8000`;
const defaultWsHost = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000/ws/live`;
const API_URL = import.meta.env.VITE_API_URL || defaultApiHost;
const WS_URL = import.meta.env.VITE_WS_URL || defaultWsHost;

const AGENTS = [
  { name: "Triage Agent", accent: "signal", role: "Detects anomalies from live telemetry" },
  { name: "Forensics Agent", accent: "amber", role: "Correlates history, identity, host, and network context" },
  { name: "Decision Agent", accent: "sky", role: "Scores risk and explains the threat narrative" },
  { name: "Action Agent", accent: "danger", role: "Blocks, notifies, logs, and learns from feedback" }
];

const initialThoughts = AGENTS.map((agent) => ({
  agent: agent.name,
  thought: "Standing by for live telemetry...",
  confidence: 0.2,
  evidence: [],
  time: new Date().toISOString()
}));

function Icon({ type, className = "h-4 w-4" }) {
  const paths = {
    shield: "M12 3l7 3v5c0 5-3.5 8.4-7 10-3.5-1.6-7-5-7-10V6l7-3z",
    bolt: "M13 2L4 14h7l-1 8 10-13h-7l0-7z",
    pause: "M8 5h3v14H8zM13 5h3v14h-3z",
    play: "M8 5v14l11-7L8 5z",
    target: "M12 3v3M12 18v3M3 12h3M18 12h3M7.8 7.8l2.1 2.1M14.1 14.1l2.1 2.1M16.2 7.8l-2.1 2.1M9.9 14.1l-2.1 2.1M12 8a4 4 0 100 8 4 4 0 000-8z",
    check: "M5 13l4 4L19 7",
    x: "M6 6l12 12M18 6L6 18"
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d={paths[type]} />
    </svg>
  );
}

function App() {
  const [logs, setLogs] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [thoughts, setThoughts] = useState(initialThoughts);
  const [connection, setConnection] = useState("connecting");
  const [riskSeries, setRiskSeries] = useState([18, 22, 19, 26, 31, 28, 35]);
  const [eventsPaused, setEventsPaused] = useState(false);
  const pausedRef = useRef(false);

  useEffect(() => {
    pausedRef.current = eventsPaused;
  }, [eventsPaused]);

  useEffect(() => {
    fetch(`${API_URL}/api/incidents`)
      .then((res) => res.json())
      .then(setIncidents)
      .catch(() => setIncidents([]));

    const socket = new WebSocket(WS_URL);
    socket.onopen = () => setConnection("online");
    socket.onclose = () => setConnection("offline");
    socket.onerror = () => setConnection("offline");
    socket.onmessage = (event) => {
      if (pausedRef.current) return;
      const message = JSON.parse(event.data);
      if (message.type === "snapshot") {
        setLogs(message.payload.logs || []);
        setIncidents(message.payload.incidents || []);
        setConnection(message.payload.health?.status === "online" ? "online" : "connecting");
      }
      if (message.type === "log") {
        setLogs((items) => [message.payload, ...items].slice(0, 24));
      }
      if (message.type === "agent_update") {
        setThoughts((items) => [message, ...items.filter((item) => item.agent !== message.agent)].slice(0, 12));
      }
      if (message.type === "incident") {
        setIncidents((items) => [message.payload, ...items.filter((item) => item.id !== message.payload.id)].slice(0, 8));
        setRiskSeries((items) => [...items.slice(-20), message.payload.risk]);
      }
      if (message.type === "override") {
        setThoughts((items) => [
          {
            agent: "Action Agent",
            thought: message.payload.message,
            confidence: 1,
            evidence: [message.payload.incident_id],
            time: new Date().toISOString()
          },
          ...items
        ]);
      }
      if (message.type === "reset") {
        setLogs([]);
        setIncidents([]);
        setRiskSeries([18, 22, 19, 26, 31, 28, 35]);
        setThoughts(initialThoughts);
      }
    };
    return () => socket.close();
  }, []);

  const currentIncident = incidents[0];
  const risk = currentIncident?.risk ?? riskSeries[riskSeries.length - 1];
  const blockedCount = incidents.filter((incident) => incident.status === "contained").length;

  const heatmap = useMemo(() => {
    return Array.from({ length: 42 }, (_, index) => {
      const incidentWeight = Math.max(0, risk - 35) / 65;
      const wave = Math.sin(index * 1.7 + risk / 15) * 0.22 + 0.45;
      return Math.min(1, wave + incidentWeight * (index % 7 > 3 ? 0.4 : 0.16));
    });
  }, [risk]);

  async function triggerAttack() {
    await fetch(`${API_URL}/api/attack`, { method: "POST" });
  }

  async function resetSimulation() {
    await fetch(`${API_URL}/api/reset`, { method: "POST" });
  }

  async function sendFeedback(label) {
    if (!currentIncident) return;
    await fetch(`${API_URL}/api/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ incident_id: currentIncident.id, label, note: "Hackathon demo operator feedback" })
    });
  }

  async function override() {
    if (!currentIncident) return;
    await fetch(`${API_URL}/api/override/${currentIncident.id}`, { method: "POST" });
  }

  return (
    <main className="min-h-screen overflow-hidden bg-bunker text-slate-100">
      <div className="scanline" />
      <header className="border-b border-line bg-bunker/90 px-5 py-4 backdrop-blur xl:px-8">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-md border border-signal/40 bg-signal/10 text-signal shadow-glow">
              <Icon type="shield" className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold tracking-normal text-white">GuardianSwarm</h1>
              <p className="text-sm text-slate-400">Autonomous multi-agent SOC replacing passive alert monitoring</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill label={connection === "online" ? "Live WebSocket" : "Reconnecting"} tone={connection === "online" ? "green" : "red"} />
            <button onClick={triggerAttack} className="command danger" title="Simulate cyberattack">
              <Icon type="target" /> Simulate Attack
            </button>
            <button onClick={resetSimulation} className="command" title="Reset simulation state">
              Reset
            </button>
            <button onClick={() => setEventsPaused((value) => !value)} className="command" title="Pause dashboard stream">
              <Icon type={eventsPaused ? "play" : "pause"} /> {eventsPaused ? "Resume" : "Pause"}
            </button>
          </div>
        </div>
      </header>

      <section className="grid gap-4 px-5 py-5 xl:grid-cols-[1.3fr_0.9fr_1fr] xl:px-8">
        <HeroPanel risk={risk} currentIncident={currentIncident} blockedCount={blockedCount} />
        <AgentMesh thoughts={thoughts} />
        <Heatmap heatmap={heatmap} />
      </section>

      <section className="grid gap-4 px-5 pb-6 xl:grid-cols-[1fr_1fr] xl:px-8">
        <LiveLogs logs={logs} />
        <IncidentTimeline incident={currentIncident} onOverride={override} onFeedback={sendFeedback} />
      </section>

      <section className="grid gap-4 px-5 pb-8 lg:grid-cols-[0.9fr_1.1fr] xl:px-8">
        <RiskGraph series={riskSeries} />
        <IncidentQueue incidents={incidents} />
      </section>
    </main>
  );
}

function StatusPill({ label, tone }) {
  const colors = tone === "green" ? "bg-signal/10 text-signal border-signal/30" : "bg-danger/10 text-danger border-danger/30";
  return <span className={`rounded-full border px-3 py-1 text-xs font-medium ${colors}`}>{label}</span>;
}

function HeroPanel({ risk, currentIncident, blockedCount }) {
  return (
    <section className="panel relative overflow-hidden p-5">
      <div className="orbital" />
      <div className="relative z-10 flex min-h-[260px] flex-col justify-between gap-6">
        <div>
          <p className="label">Autonomous incident command</p>
          <h2 className="mt-2 max-w-xl text-4xl font-semibold leading-tight text-white">Observe. Think. Act. Learn.</h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
            Agents collaborate in real time to filter noise, investigate evidence, explain intent, and contain threats without waiting for a human analyst.
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          <Metric label="Current risk" value={`${risk}%`} tone={risk > 80 ? "danger" : risk > 60 ? "amber" : "signal"} />
          <Metric label="Blocked threats" value={blockedCount} tone="signal" />
          <Metric label="Active incident" value={currentIncident?.id || "None"} tone="sky" />
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, tone }) {
  const color = tone === "danger" ? "text-danger" : tone === "amber" ? "text-amber" : tone === "sky" ? "text-sky-300" : "text-signal";
  return (
    <div className="metric">
      <span>{label}</span>
      <strong className={color}>{value}</strong>
    </div>
  );
}

function AgentMesh({ thoughts }) {
  return (
    <section className="panel p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="label">Agent collaboration</p>
          <h3 className="section-title">Live thinking mesh</h3>
        </div>
        <Icon type="bolt" className="h-5 w-5 text-signal" />
      </div>
      <div className="agent-grid">
        {AGENTS.map((agent, index) => {
          const latest = thoughts.find((item) => item.agent === agent.name);
          return (
            <div key={agent.name} className="agent-node">
              <div className={`pulse-dot dot-${agent.accent}`} />
              <div>
                <p className="font-medium text-white">{agent.name}</p>
                <p className="mt-1 text-xs text-slate-400">{agent.role}</p>
                <p className="mt-3 text-sm leading-5 text-slate-200">{latest?.thought}</p>
                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-800">
                  <div className="h-full rounded-full bg-signal transition-all" style={{ width: `${(latest?.confidence || 0.2) * 100}%` }} />
                </div>
              </div>
              {index < AGENTS.length - 1 && <span className="connector" />}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function Heatmap({ heatmap }) {
  return (
    <section className="panel p-5">
      <p className="label">Threat heatmap</p>
      <h3 className="section-title">Attack surface pressure</h3>
      <div className="mt-5 grid grid-cols-7 gap-2">
        {heatmap.map((value, index) => (
          <div
            key={index}
            className="aspect-square rounded border border-white/5 transition-all"
            style={{
              background: value > 0.78 ? `rgba(255,92,124,${value})` : value > 0.55 ? `rgba(248,184,78,${value})` : `rgba(25,240,182,${value * 0.7})`,
              boxShadow: value > 0.72 ? "0 0 18px rgba(255,92,124,0.28)" : "none"
            }}
          />
        ))}
      </div>
      <div className="mt-5 flex items-center justify-between text-xs text-slate-400">
        <span>Identity</span>
        <span>Endpoint</span>
        <span>Cloud</span>
        <span>Egress</span>
      </div>
    </section>
  );
}

function LiveLogs({ logs }) {
  return (
    <section className="panel p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="label">Live log stream</p>
          <h3 className="section-title">Noise filtered into evidence</h3>
        </div>
        <span className="text-xs text-slate-400">{logs.length} recent events</span>
      </div>
      <div className="log-table">
        {logs.map((log) => (
          <div key={log.id} className="log-row">
            <span className={`severity severity-${log.severity}`}>{log.severity}</span>
            <span className="font-mono text-xs text-slate-500">{log.source}</span>
            <span className="truncate text-slate-200">{log.message}</span>
            <span className="hidden font-mono text-xs text-slate-500 md:block">{log.ip}</span>
          </div>
        ))}
        {logs.length === 0 && <p className="empty">Waiting for telemetry from the backend...</p>}
      </div>
    </section>
  );
}

function IncidentTimeline({ incident, onOverride, onFeedback }) {
  const timeline = incident?.timeline || [];
  return (
    <section className="panel p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="label">Incident timeline</p>
          <h3 className="section-title">{incident?.title || "Awaiting confirmed anomaly"}</h3>
        </div>
        <div className="flex gap-2">
          <button onClick={onOverride} disabled={!incident} className="icon-command" title="Manual override">
            <Icon type="x" />
          </button>
          <button onClick={() => onFeedback("true-positive")} disabled={!incident} className="icon-command" title="Mark true positive">
            <Icon type="check" />
          </button>
          <button onClick={() => onFeedback("false-positive")} disabled={!incident} className="icon-command" title="Mark false positive">
            FP
          </button>
        </div>
      </div>
      <div className="timeline">
        {timeline.slice(-8).map((item, index) => (
          <div key={`${item.time}-${index}`} className="timeline-item">
            <span className="timeline-dot" />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <strong>{item.phase}</strong>
                <span>{item.agent}</span>
              </div>
              <p>{item.detail}</p>
            </div>
          </div>
        ))}
        {timeline.length === 0 && <p className="empty">Observe - Think - Act - Learn will populate during the attack simulation.</p>}
      </div>
    </section>
  );
}

function RiskGraph({ series }) {
  const points = series.map((value, index) => {
    const x = (index / Math.max(series.length - 1, 1)) * 100;
    const y = 100 - value;
    return `${x},${y}`;
  }).join(" ");
  return (
    <section className="panel p-5">
      <p className="label">Risk graph</p>
      <h3 className="section-title">Autonomous confidence over time</h3>
      <svg className="mt-5 h-48 w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <linearGradient id="riskGradient" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#19f0b6" />
            <stop offset="55%" stopColor="#f8b84e" />
            <stop offset="100%" stopColor="#ff5c7c" />
          </linearGradient>
        </defs>
        {[20, 40, 60, 80].map((line) => <line key={line} x1="0" x2="100" y1={100 - line} y2={100 - line} stroke="rgba(255,255,255,.08)" strokeWidth=".4" />)}
        <polyline points={points} fill="none" stroke="url(#riskGradient)" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </section>
  );
}

function IncidentQueue({ incidents }) {
  return (
    <section className="panel p-5">
      <p className="label">Incident queue</p>
      <h3 className="section-title">Autonomous case memory</h3>
      <div className="mt-4 grid gap-3">
        {incidents.map((incident) => (
          <div key={incident.id} className="incident-card">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-mono text-xs text-signal">{incident.id}</p>
                <h4 className="mt-1 font-medium text-white">{incident.title}</h4>
                <p className="mt-2 text-sm leading-5 text-slate-300">{incident.reasoning}</p>
              </div>
              <span className={`risk-badge ${incident.risk > 80 ? "risk-high" : "risk-mid"}`}>{incident.risk}%</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
              <span>{incident.status}</span>
              <span>{incident.kill_chain_stage}</span>
              <span>{incident.action}</span>
            </div>
          </div>
        ))}
        {incidents.length === 0 && <p className="empty">No incidents yet. Trigger the demo attack to watch the swarm build a case.</p>}
      </div>
    </section>
  );
}

createRoot(document.getElementById("root")).render(<App />);
