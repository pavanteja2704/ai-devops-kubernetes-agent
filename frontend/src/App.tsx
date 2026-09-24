import { useEffect, useMemo, useState } from "react";
import { api, loadClusterData } from "./api";
import type { AnalysisResult, ClusterData, Deployment, Event, Node, Pod } from "./types";

type Page = "dashboard" | "troubleshooter" | "pods" | "deployments" | "nodes" | "events";

const navItems: Array<{ id: Page; label: string; icon: string }> = [
  { id: "dashboard", label: "Dashboard", icon: "◈" },
  { id: "troubleshooter", label: "AI Troubleshooter", icon: "✦" },
  { id: "pods", label: "Pods", icon: "⬡" },
  { id: "deployments", label: "Deployments", icon: "▣" },
  { id: "nodes", label: "Nodes", icon: "⌘" },
  { id: "events", label: "Events", icon: "!" },
];

const healthQuestion =
  "Check the current Kubernetes cluster health. Look at pods, deployments, services, nodes, and recent warning events. Identify any obvious problems and explain what you find.";

function formatValue(value: unknown, fallback = "—"): string {
  return value === undefined || value === null || value === "" ? fallback : String(value);
}

function statusTone(status?: string): "good" | "warn" | "bad" | "neutral" {
  const normalized = status?.toLowerCase() || "";
  if (["running", "true", "healthy", "ready", "active", "succeeded"].some((item) => normalized.includes(item))) return "good";
  if (["warning", "pending", "unknown", "terminating"].some((item) => normalized.includes(item))) return "warn";
  if (["failed", "false", "crash", "error", "unhealthy"].some((item) => normalized.includes(item))) return "bad";
  return "neutral";
}

function Badge({ children, tone = "neutral" }: { children: React.ReactNode; tone?: "good" | "warn" | "bad" | "neutral" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function MetricCard({ label, value, detail, accent }: { label: string; value: number | string; detail: string; accent: string }) {
  return (
    <div className={`metric-card ${accent}`}>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
      <span className="metric-detail">{detail}</span>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

function AnalysisPanel({ result }: { result: AnalysisResult | null }) {
  if (!result) return null;
  const status = result.status || "unknown";
  const copyCommand = async (command: string) => {
    await navigator.clipboard.writeText(command);
  };
  return (
    <section className={`analysis-panel incident-${status}`}>
      <div className="incident-header">
        <div>
          <span className="eyebrow">AI incident assessment</span>
          <h2>{result.problem?.title || "Cluster assessment"}</h2>
        </div>
        <Badge tone={status === "critical" ? "bad" : status === "warning" ? "warn" : status === "healthy" ? "good" : "neutral"}>{status.toUpperCase()}</Badge>
      </div>
      <div className="problem-card">
        <span className="eyebrow">Problem</span>
        <div className="problem-grid">
          <div><span>Resource</span><strong>{formatValue(result.problem?.resource_type)}: {formatValue(result.problem?.resource_name)}</strong></div>
          <div><span>Namespace</span><strong>{formatValue(result.problem?.namespace)}</strong></div>
          <div><span>State</span><strong>{formatValue(result.problem?.current_state)}</strong></div>
          <div><span>Impact</span><strong>{formatValue(result.problem?.impact)}</strong></div>
        </div>
      </div>
      <div className="analysis-grid">
        <AnalysisBlock title="Root cause" text={result.root_cause?.summary} meta={result.root_cause?.confidence ? `Confidence: ${result.root_cause.confidence.toUpperCase()}` : undefined} />
        <AnalysisBlock title="Evidence" items={result.root_cause?.evidence} empty="No evidence was returned." check />
        <div className="analysis-block action-block"><h3>Recommended actions</h3>{result.recommended_actions?.length ? result.recommended_actions.map((action, index) => <div className="action-card" key={`${action.title}-${index}`}><div className="action-title"><strong>{action.priority || index + 1}. {action.title}</strong><Badge tone={action.risk === "high" ? "bad" : action.risk === "medium" ? "warn" : "good"}>{action.risk || "low"} risk</Badge></div><p>{action.description}</p>{action.command && <CommandBox command={action.command} onCopy={copyCommand} />}</div>) : <p className="muted">No actions returned.</p>}</div>
        <div className="analysis-block"><h3>Verification</h3>{result.verification?.length ? result.verification.map((item, index) => <div className="verification-item" key={`${item.description}-${index}`}><p>{item.description}</p>{item.command && <CommandBox command={item.command} onCopy={copyCommand} />}</div>) : <p className="muted">No verification steps returned.</p>}</div>
        <AnalysisBlock title="What NOT to do" items={result.what_not_to_do} empty="No restrictions returned." warning />
        <AnalysisBlock title="Limitations" items={result.limitations} empty="No limitations returned." />
      </div>
    </section>
  );
}

function CommandBox({ command, onCopy }: { command: string; onCopy: (command: string) => Promise<void> }) {
  const [copied, setCopied] = useState(false);
  return <div className="command-box"><code>{command}</code><button onClick={() => { void onCopy(command).then(() => { setCopied(true); window.setTimeout(() => setCopied(false), 1500); }); }}>{copied ? "Copied" : "Copy"}</button></div>;
}

function AnalysisBlock({ title, text, meta, items, empty, check, warning }: { title: string; text?: string; meta?: string; items?: string[]; empty?: string; check?: boolean; warning?: boolean }) {
  return (
    <div className="analysis-block">
      <h3>{warning && "⚠ "}{title}</h3>
      {text ? <><p>{text}</p>{meta && <span className="confidence">{meta}</span>}</> : items?.length ? <ul className={check ? "check-list" : ""}>{items.map((item, index) => <li key={`${item}-${index}`}>{check && "✓ "}{item}</li>)}</ul> : <p className="muted">{empty}</p>}
    </div>
  );
}

function DataTable<T>({ columns, rows, rowKey, onRowClick }: { columns: Array<{ label: string; render: (row: T) => React.ReactNode }>; rows: T[]; rowKey: (row: T, index: number) => string; onRowClick?: (row: T) => void }) {
  if (!rows.length) return <EmptyState message="No data returned from the cluster." />;
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{columns.map((column) => <th key={column.label}>{column.label}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={rowKey(row, index)} onClick={() => onRowClick?.(row)} className={onRowClick ? "clickable-row" : ""}>{columns.map((column) => <td key={column.label}>{column.render(row)}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

function PodsView({ pods, onPodClick }: { pods: Pod[]; onPodClick: (pod: Pod) => void }) {
  return <PageShell eyebrow="Workloads" title="Pods" description="Live pod health, placement, and restart signals.">
    <DataTable
      rows={pods}
      rowKey={(pod, index) => `${pod.namespace}-${pod.name}-${index}`}
      onRowClick={onPodClick}
      columns={[
        { label: "Pod", render: (pod) => <div><strong>{formatValue(pod.name)}</strong><span className="table-sub">{formatValue(pod.namespace)}</span></div> },
        { label: "Status", render: (pod) => <Badge tone={statusTone(pod.phase)}>{formatValue(pod.phase)}</Badge> },
        { label: "Restarts", render: (pod) => Object.values(pod.restart_counts || {}).reduce((total, count) => total + count, 0) },
        { label: "Node", render: (pod) => formatValue(pod.node) },
        { label: "Ready state", render: (pod) => <span>{(pod.container_states || []).map((state) => state.state).join(", ") || "Unknown"}</span> },
      ]}
    />
  </PageShell>;
}

function DeploymentsView({ deployments }: { deployments: Deployment[] }) {
  return <PageShell eyebrow="Workloads" title="Deployments" description="Replica availability across every namespace.">
    <DataTable rows={deployments} rowKey={(item, index) => `${item.namespace}-${item.name}-${index}`} columns={[
      { label: "Deployment", render: (item) => <div><strong>{formatValue(item.name)}</strong><span className="table-sub">{formatValue(item.namespace)}</span></div> },
      { label: "Desired", render: (item) => formatValue(item.desired_replicas, "0") },
      { label: "Available", render: (item) => formatValue(item.available_replicas, "0") },
      { label: "Ready", render: (item) => formatValue(item.ready_replicas, "0") },
      { label: "Health", render: (item) => <Badge tone={item.ready_replicas === item.desired_replicas ? "good" : "warn"}>{item.ready_replicas === item.desired_replicas ? "Healthy" : "Degraded"}</Badge> },
    ]} />
  </PageShell>;
}

function NodesView({ nodes }: { nodes: Node[] }) {
  return <PageShell eyebrow="Infrastructure" title="Nodes" description="Capacity and readiness across the connected cluster.">
    <DataTable rows={nodes} rowKey={(item, index) => `${item.name}-${index}`} columns={[
      { label: "Node", render: (item) => <strong>{formatValue(item.name)}</strong> },
      { label: "Status", render: (item) => <Badge tone={statusTone(item.status)}>{formatValue(item.status)}</Badge> },
      { label: "CPU capacity", render: (item) => formatValue(item.cpu_capacity) },
      { label: "Memory capacity", render: (item) => formatValue(item.memory_capacity) },
      { label: "Kubernetes", render: (item) => formatValue(item.kubernetes_version) },
    ]} />
  </PageShell>;
}

function EventsView({ events }: { events: Event[] }) {
  return <PageShell eyebrow="Signals" title="Events" description="Recent cluster signals, with warnings surfaced first.">
    <DataTable rows={[...events].sort((a, b) => (a.type === "Warning" ? -1 : 1) - (b.type === "Warning" ? -1 : 1))} rowKey={(item, index) => `${item.namespace}-${item.name}-${index}`} columns={[
      { label: "Timestamp", render: (item) => formatValue(item.last_timestamp || item.first_timestamp) },
      { label: "Type", render: (item) => <Badge tone={item.type === "Warning" ? "warn" : "neutral"}>{formatValue(item.type)}</Badge> },
      { label: "Resource", render: (item) => <div><strong>{formatValue(item.name)}</strong><span className="table-sub">{formatValue(item.namespace)}</span></div> },
      { label: "Reason", render: (item) => formatValue(item.reason) },
      { label: "Message", render: (item) => <span className="event-message">{formatValue(item.message)}</span> },
    ]} />
  </PageShell>;
}

function PageShell({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children: React.ReactNode }) {
  return <main className="content"><div className="page-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div></div>{children}</main>;
}

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [data, setData] = useState<ClusterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [question, setQuestion] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [selectedPod, setSelectedPod] = useState<Pod | null>(null);
  const [logs, setLogs] = useState("");
  const [logsLoading, setLogsLoading] = useState(false);

  const refresh = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    setError("");
    try {
      setData(await loadClusterData());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach the backend.");
      if (!data) {
        try { setData(await loadClusterData()); } catch (fallbackErr) { setError(fallbackErr instanceof Error ? fallbackErr.message : "Unable to reach the backend."); }
      }
    } finally { if (showLoading) setLoading(false); }
  };

  useEffect(() => { void refresh(); }, []);
  useEffect(() => {
    const timer = window.setInterval(() => { void refresh(false); }, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const runAnalysis = async (prompt: string) => {
    setAnalyzing(true);
    setError("");
    try { setAnalysis(await api.analyze(prompt)); setPage("troubleshooter"); } catch (err) { setError(err instanceof Error ? err.message : "Analysis failed."); } finally { setAnalyzing(false); }
  };

  const runHealthTest = async () => {
    setLoading(true);
    setError("");
    try {
      setData(await loadClusterData());
      await runAnalysis(healthQuestion);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to refresh cluster telemetry.");
    } finally {
      setLoading(false);
    }
  };

  const openPod = async (pod: Pod) => {
    setSelectedPod(pod);
    setLogs("");
    if (!pod.namespace || !pod.name) return;
    setLogsLoading(true);
    try { setLogs((await api.logs(pod.namespace, pod.name, pod.container_states?.[0]?.name)).logs); } catch (err) { setLogs(err instanceof Error ? err.message : "Logs unavailable."); } finally { setLogsLoading(false); }
  };

  const summary = useMemo(() => {
    if (!data) return "Waiting for cluster telemetry";
    const warningCount = data.events.filter((event) => event.type === "Warning").length;
    return warningCount ? `${warningCount} warning signal${warningCount === 1 ? "" : "s"} require review` : "No warning events detected";
  }, [data]);

  return <div className="app-shell">
    <aside className="sidebar">
      <div className="brand"><div className="brand-mark">✦</div><div><strong>Control Room</strong><span>AI DevOps Agent</span></div></div>
      <div className="cluster-card"><span className="eyebrow">Connected cluster</span><div className="cluster-name"><span className={`status-dot ${data?.status.available ? "online" : ""}`} />{data?.status.context || "Loading..."}</div><span className="cluster-meta">{data?.status.available ? "Kubernetes API online" : "Connection unavailable"}</span></div>
      <nav>{navItems.map((item) => <button key={item.id} className={page === item.id ? "nav-item active" : "nav-item"} onClick={() => setPage(item.id)}><span>{item.icon}</span>{item.label}</button>)}</nav>
      <div className="sidebar-footer"><Badge tone="good">Read-only mode</Badge><span>Human review required for remediation</span></div>
    </aside>
    <div className="main-area">
      <header className="topbar"><div className="mobile-brand">✦ AI DevOps</div><div className="topbar-actions"><span className="api-label">API <Badge tone={data?.status.available ? "good" : "bad"}>{data?.status.available ? "Connected" : "Offline"}</Badge></span><button className="icon-button" onClick={() => void refresh()} aria-label="Refresh cluster data">↻</button></div></header>
      {error && <div className="error-banner"><strong>Backend error:</strong> {error}<button onClick={() => setError("")}>Dismiss</button></div>}
      {loading ? <main className="content loading-state"><div className="spinner" /><p>Connecting to cluster telemetry...</p></main> : !data ? <main className="content"><EmptyState message="The backend could not provide cluster telemetry. Check VITE_API_BASE_URL and try again." /></main> :
        page === "dashboard" ? <Dashboard data={data} summary={summary} onHealthTest={() => void runHealthTest()} analyzing={analyzing} onNavigate={setPage} /> :
        page === "troubleshooter" ? <Troubleshooter analysis={analysis} question={question} setQuestion={setQuestion} onSubmit={() => void runAnalysis(question)} analyzing={analyzing} /> :
        page === "pods" ? <PodsView pods={data.pods} onPodClick={(pod) => void openPod(pod)} /> :
        page === "deployments" ? <DeploymentsView deployments={data.deployments} /> :
        page === "nodes" ? <NodesView nodes={data.nodes} /> : <EventsView events={data.events} />}
    </div>
    {selectedPod && <div className="modal-backdrop" onClick={() => setSelectedPod(null)}><div className="pod-modal" onClick={(event) => event.stopPropagation()}><div className="modal-heading"><div><span className="eyebrow">Pod details</span><h2>{selectedPod.name}</h2><p>{selectedPod.namespace}</p></div><button className="icon-button" onClick={() => setSelectedPod(null)}>×</button></div><div className="detail-grid"><div><span>Status</span><strong>{formatValue(selectedPod.phase)}</strong></div><div><span>Node</span><strong>{formatValue(selectedPod.node)}</strong></div><div><span>Created</span><strong>{formatValue(selectedPod.creation_timestamp)}</strong></div></div><h3>Container logs</h3>{logsLoading ? <div className="logs-loading"><div className="spinner" /> Loading logs...</div> : <pre className="logs">{logs || "No logs returned."}</pre>}</div></div>}
  </div>;
}

function Dashboard({ data, summary, onHealthTest, analyzing, onNavigate }: { data: ClusterData; summary: string; onHealthTest: () => void; analyzing: boolean; onNavigate: (page: Page) => void }) {
  const warningCount = data.events.filter((event) => event.type === "Warning").length;
  const unhealthyPods = data.pods.filter((pod) => statusTone(pod.phase) === "bad").length;
  return <PageShell eyebrow="Overview" title="Cluster dashboard" description="A live read-only view of your Kubernetes control plane and workloads.">
    <div className="hero-card"><div><span className="eyebrow">Health posture</span><h2>{summary}</h2><p>Telemetry from <strong>{data.status.context}</strong> · refreshed from the Kubernetes API</p></div><button className="primary-button" onClick={onHealthTest} disabled={analyzing}>{analyzing ? "Analyzing..." : "✦ Run Health Test"}</button></div>
    <div className="metrics-grid"><MetricCard label="Nodes" value={data.nodes.length} detail="Cluster capacity" accent="purple" /><MetricCard label="Pods" value={data.pods.length} detail={unhealthyPods ? `${unhealthyPods} need attention` : "All reporting"} accent="blue" /><MetricCard label="Deployments" value={data.deployments.length} detail="Workload controllers" accent="cyan" /><MetricCard label="Services" value={data.services.length} detail="Network endpoints" accent="green" /><MetricCard label="Warnings" value={warningCount} detail={warningCount ? "Review recommended" : "No warnings"} accent="orange" /></div>
    <div className="dashboard-grid"><section className="panel"><div className="section-heading"><div><span className="eyebrow">Signals</span><h2>Recent warning events</h2></div><button className="text-button" onClick={() => onNavigate("events")}>View all →</button></div>{data.events.filter((event) => event.type === "Warning").slice(0, 5).map((event, index) => <div className="signal-row" key={`${event.name}-${index}`}><div className="signal-icon">!</div><div><strong>{formatValue(event.reason)}</strong><span>{formatValue(event.message)}</span></div><time>{formatValue(event.last_timestamp, "Recent")}</time></div>)}{!warningCount && <EmptyState message="No warning events were reported." />}</section><section className="panel"><div className="section-heading"><div><span className="eyebrow">Workloads</span><h2>Deployment readiness</h2></div><button className="text-button" onClick={() => onNavigate("deployments")}>View all →</button></div>{data.deployments.slice(0, 5).map((deployment, index) => <div className="deployment-row" key={`${deployment.name}-${index}`}><div><strong>{formatValue(deployment.name)}</strong><span>{formatValue(deployment.namespace)}</span></div><div className="replica-bar"><span style={{ width: `${Math.min(100, ((deployment.ready_replicas || 0) / Math.max(1, deployment.desired_replicas || 1)) * 100)}%` }} /></div><span>{formatValue(deployment.ready_replicas, "0")}/{formatValue(deployment.desired_replicas, "0")}</span></div>)}</section></div>
  </PageShell>;
}

function Troubleshooter({ analysis, question, setQuestion, onSubmit, analyzing }: { analysis: AnalysisResult | null; question: string; setQuestion: (value: string) => void; onSubmit: () => void; analyzing: boolean }) {
  const examples = ["Why is my cluster unhealthy?", "Why is this pod failing?", "Are there any scheduling problems?", "What are the most serious warning events?", "How do I fix this?", "What command should I run?", "Is it safe to delete this resource?", "How do I verify the fix?"];
  return <PageShell eyebrow="Intelligence" title="AI troubleshooter" description="Ask questions about the current cluster. Every answer is grounded in read-only telemetry."><section className="chat-card"><div className="chat-orb">✦</div><div><h2>What would you like to investigate?</h2><p>Gemini will analyze the latest pods, workloads, nodes, services, and warning events.</p></div><form onSubmit={(event) => { event.preventDefault(); if (question.trim()) onSubmit(); }}><textarea aria-label="Ask about your Kubernetes cluster" placeholder="Ask about your Kubernetes cluster..." value={question} onChange={(event) => setQuestion(event.target.value)} /><div className="chat-form-footer"><div className="example-chips">{examples.map((example) => <button type="button" key={example} onClick={() => setQuestion(example)}>{example}</button>)}</div><button className="primary-button" disabled={analyzing || !question.trim()}>{analyzing ? "Thinking..." : "Ask Gemini →"}</button></div></form></section><AnalysisPanel result={analysis} /></PageShell>;
}
