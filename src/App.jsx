import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Books,
  ChartLineUp,
  CheckCircle,
  Clock,
  Database,
  Flask,
  FlowArrow,
  GlobeHemisphereEast,
  House,
  ListChecks,
  MagnifyingGlass,
  Pulse,
  Scales,
  ShieldCheck,
  Storefront,
  Strategy,
  UserFocus,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API = window.location.port === "5173" ? "http://127.0.0.1:8000/api" : "/api";
const COLORS = ["#c9454e", "#dc8b2a", "#218982", "#3476bc", "#7b8da4", "#b6c2cf"];
const nav = [
  ["overview", "Command Center", House],
  ["emerging", "Emerging Risks", Pulse],
  ["queue", "Review Queue", ListChecks],
  ["advertisers", "Advertiser Integrity", Storefront],
  ["policy", "Policy Studio", Books],
  ["strategy", "Strategy Builder", Strategy],
  ["evaluation", "Strategy Evaluation", Scales],
  ["metrics", "Metric Diagnosis", ChartLineUp],
  ["benchmark", "Benchmark Lab", Flask],
  ["feedback", "Human Feedback", UserFocus],
  ["evidence", "Public Evidence", GlobeHemisphereEast],
  ["readiness", "Launch Readiness", ShieldCheck],
  ["provenance", "System & Data", Database],
];

async function api(path, options) {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}
const fmt = new Intl.NumberFormat("en-US");
const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});
const pct = (value) =>
  `${(Number(value || 0) * 100).toFixed(Number(value || 0) > 0 && Number(value || 0) < 0.01 ? 1 : 0)}%`;
const short = (value, length = 110) =>
  value?.length > length ? `${value.slice(0, length)}…` : value || "—";
const legendLabel = (value) => short(String(value), 35);

function Pill({ children, tone = "neutral" }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}
function Empty({ title, detail }) {
  return (
    <div className="empty">
      <Database size={24} />
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}
function PageHeader({ title, subtitle, eyebrow, updated, actions }) {
  return (
    <div className="page-header">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
      {updated ? (
        <div className="updated">
          <Clock size={20} />
          <span>
            Data updates after ingestion
            <small>Last scored {new Date(updated).toLocaleString()}</small>
          </span>
        </div>
      ) : (
        actions
      )}
    </div>
  );
}
function Boundary({ children, tone = "blue" }) {
  return (
    <div className={`boundary ${tone}`}>
      <ShieldCheck size={18} />
      <span>{children}</span>
    </div>
  );
}
function DataState({ loading, error, children }) {
  if (loading)
    return <Empty title="Loading product evidence" detail="Reading the scoped analytical mart." />;
  if (error) return <Empty title="This product surface is unavailable" detail={error} />;
  return children;
}
function useEndpoint(path, initial = null) {
  const [data, setData] = useState(initial);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await api(path));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    load();
  }, [load]);
  return { data, setData, error, loading, reload: load };
}

function SourceStrip({ sources = [] }) {
  return (
    <section className="surface provenance">
      <div className="section-title">
        Source provenance <span>Every real-data KPI traces to declared public records.</span>
      </div>
      <div className="source-grid">
        {sources.map((source) => (
          <div className="source" key={source.key}>
            <div className={`source-icon ${source.key}`}>
              <Database size={23} />
            </div>
            <div>
              <strong>{source.name}</strong>
              <small>
                <i className={source.status} />
                {source.status === "optional"
                  ? "Optional enrichment"
                  : `${fmt.format(source.records)} records`}
              </small>
            </div>
            <span>{source.detail}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
function LifecycleStrip({ navigate }) {
  const strategies = useEndpoint("/strategies");
  const benchmark = useEndpoint("/benchmark-lab");
  const readiness = useEndpoint("/launch-readiness");
  if (
    strategies.loading ||
    benchmark.loading ||
    readiness.loading ||
    strategies.error ||
    benchmark.error ||
    readiness.error
  )
    return null;
  const active = strategies.data?.active_version;
  const candidate = strategies.data?.candidate_version;
  const gatePass = benchmark.data?.promotion_gate?.status === "eligible_for_review";
  const items = [
    ["Enforced strategy", active?.version_id, "enforced", "strategy"],
    ["Shadow candidate", candidate?.version_id, "non-authoritative", "strategy"],
    ["Policy packs", candidate?.policy_pack_ids?.length, "demo configuration", "policy"],
    [
      "Benchmark gate",
      gatePass ? "ready for review" : "hold promotion",
      `${benchmark.data?.promotion_gate?.blockers?.length || 0} quality blockers`,
      "benchmark",
    ],
    [
      "Production gate",
      readiness.data?.status === "eligible_for_controlled_promotion" ? "ready" : "HOLD",
      `${readiness.data?.blockers?.length || 0} launch blockers`,
      "readiness",
    ],
  ];
  return (
    <section className="lifecycle-strip" aria-label="Risk strategy lifecycle status">
      {items.map(([label, value, note, page]) => (
        <button key={label} onClick={() => navigate(page)}>
          <span>{label}</span>
          <strong>{value}</strong>
          <small>{note}</small>
          <ArrowRight size={15} />
        </button>
      ))}
    </section>
  );
}
function Kpis({ overview }) {
  const values = [
    ["Total real records", overview.total_real_records, "FTC + CFPB + authorized Meta"],
    ["Cases analyzed", overview.cases_analyzed, "Deterministic workflow"],
    ["High-priority signals", overview.high_risk_cases, pct(overview.high_risk_rate)],
    ["Analyst queue", overview.review_queue_size, "Human judgment retained"],
    ["Capacity released", overview.estimated_minutes_saved, "Estimated minutes"],
  ];
  return (
    <section className="surface kpis">
      {values.map(([label, value, note]) => (
        <div className="kpi" key={label}>
          <span>{label}</span>
          <strong>{fmt.format(value || 0)}</strong>
          <small>{note}</small>
        </div>
      ))}
    </section>
  );
}
function RiskTable({ cases = [], onSelect, compact = false }) {
  if (!cases.length)
    return (
      <Empty
        title="No cases in this scope"
        detail="No records are being fabricated to fill the table."
      />
    );
  return (
    <div className="table-wrap">
      <table className="risk-table">
        <thead>
          <tr>
            <th>Scope</th>
            <th>Case</th>
            <th>Risk category</th>
            <th>Priority</th>
            {!compact && <th>Routing</th>}
            <th>
              <span className="sr-only">Open</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {cases.map((item) => (
            <tr key={item.case_id}>
              <td>
                <Pill tone={item.source.toLowerCase()}>{item.source}</Pill>
              </td>
              <td>
                <strong>{item.case_id}</strong>
                <span>{short(item.case_text, compact ? 60 : 100)}</span>
              </td>
              <td>{item.risk_category}</td>
              <td>
                <Pill tone={item.severity}>{item.severity}</Pill>
              </td>
              {!compact && <td>{item.recommended_action}</td>}
              <td>
                <button
                  className="row-open"
                  aria-label={`Investigate ${item.case_id}`}
                  onClick={() => onSelect(item.case_id)}
                >
                  <ArrowRight size={16} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TraceValue({ step }) {
  if (Array.isArray(step.value)) {
    if (!step.value.length) return <p className="trace-empty">None recorded in this scope</p>;
    if (step.component === "Positive exceptions")
      return (
        <div className="trace-exceptions">
          {step.value.map((item) => (
            <div key={item.exception_id}>
              <strong>{item.name}</strong>
              <span>
                {(item.matched_terms || []).join(", ")} · reduction {item.applied_reduction} ·{" "}
                {item.application_status || (item.blocked_from_override ? "blocked" : "matched")}
              </span>
            </div>
          ))}
        </div>
      );
    return (
      <div className="trace-chips">
        {step.value.slice(0, 8).map((item, index) => (
          <span key={index}>
            {typeof item === "string"
              ? item
              : item.name || item.term || item.exception_id || JSON.stringify(item)}
          </span>
        ))}
      </div>
    );
  }
  if (step.value && typeof step.value === "object")
    return (
      <dl className="trace-components">
        {Object.entries(step.value).map(([key, value]) => (
          <div key={key}>
            <dt>{key.replaceAll("_", " ")}</dt>
            <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
          </div>
        ))}
      </dl>
    );
  return <p>{String(step.value)}</p>;
}

function CaseDrawer({ caseId, onClose, feedbackWritable, onFeedback }) {
  const [detail, setDetail] = useState(null);
  const [decision, setDecision] = useState("escalate");
  const [notes, setNotes] = useState("");
  const [reviewerId, setReviewerId] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [retry, setRetry] = useState(0);
  const drawerRef = useRef(null);
  const closeRef = useRef(null);
  useEffect(() => {
    let active = true;
    setDetail(null);
    setDetailError("");
    api(`/cases/${caseId}`)
      .then((value) => {
        if (!active) return;
        setDetail(value);
        setDecision(value.decision_scope === "risk_prior" ? "relevant prior" : "escalate");
        setNotes("");
        setSaved(false);
      })
      .catch((error) => {
        if (active) setDetailError(error.message);
      });
    return () => {
      active = false;
    };
  }, [caseId, retry]);
  useEffect(() => {
    const origin = document.activeElement;
    closeRef.current?.focus();
    const keydown = (event) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = [
        ...drawerRef.current.querySelectorAll(
          "button, a, textarea, input, select, [tabindex]:not([tabindex='-1'])",
        ),
      ].filter((node) => !node.disabled);
      if (!focusable.length) return;
      const [first] = focusable;
      const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", keydown);
    return () => {
      document.removeEventListener("keydown", keydown);
      origin?.focus?.();
    };
  }, [onClose]);
  const submit = async () => {
    setError("");
    if (!reviewerId.trim()) {
      setError("Reviewer identity is required.");
      return;
    }
    try {
      await api("/feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Reviewer-Id": reviewerId.trim(),
          "X-Reviewer-Role": "reviewer",
        },
        body: JSON.stringify({ case_id: caseId, decision, notes }),
      });
      setSaved(true);
      onFeedback?.();
    } catch (e) {
      setError(e.message);
    }
  };
  return (
    <div
      className="drawer-backdrop"
      onMouseDown={(event) => event.target === event.currentTarget && onClose()}
    >
      <aside
        ref={drawerRef}
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="case-drawer-title"
      >
        <header>
          <div>
            <span>Investigation Desk</span>
            <h2 id="case-drawer-title">{caseId}</h2>
          </div>
          <button
            ref={closeRef}
            className="icon-button"
            aria-label="Close case detail"
            onClick={onClose}
          >
            <X size={20} />
          </button>
        </header>
        {detailError ? (
          <div className="drawer-section">
            <Empty title="Case detail unavailable" detail={detailError} />
            <button className="primary" onClick={() => setRetry((value) => value + 1)}>
              Retry case detail
            </button>
          </div>
        ) : !detail ? (
          <Empty title="Loading decision trace" detail="Reading evidence and strategy lineage." />
        ) : (
          <>
            <div className="case-hero">
              <div>
                <Pill tone={detail.source.toLowerCase()}>{detail.source}</Pill>
                <Pill tone={detail.severity}>{detail.severity}</Pill>
              </div>
              <div className="score">
                <span>Priority score</span>
                <strong>{Math.round(detail.risk_score * 100)}</strong>
                <small>/ 100</small>
              </div>
            </div>
            <Boundary tone={detail.decision_scope === "risk_prior" ? "amber" : "blue"}>
              {detail.decision_scope === "risk_prior"
                ? "Public complaint prior · research routing only · never an ad enforcement decision."
                : "Authorized public-ad triage scope."}
            </Boundary>
            <section className="drawer-summary" aria-label="Operator decision summary">
              <div>
                <span>Risk category</span>
                <strong>{detail.risk_category}</strong>
              </div>
              <div>
                <span>Authoritative route</span>
                <strong>{detail.recommended_action}</strong>
              </div>
              <div>
                <span>Review ownership</span>
                <strong>
                  {detail.needs_human_review ? "Human decision required" : "Automation eligible"}
                </strong>
              </div>
              <div>
                <span>Detected language</span>
                <strong>{detail.language}</strong>
              </div>
            </section>
            <section className="drawer-section">
              <h3>Source record</h3>
              <p className="case-copy">{detail.case_text}</p>
              <p className="microcopy">
                Priority score is not a calibrated probability of violation.
              </p>
            </section>
            <section className="drawer-section">
              <div className="section-title">
                Decision trace <span>{detail.decision_trace.evaluated_strategy}</span>
              </div>
              <div className="trace-list">
                {detail.decision_trace.steps.map((step) => (
                  <div key={step.step}>
                    <b>{step.step}</b>
                    <div>
                      <strong>{step.component}</strong>
                      <TraceValue step={step} />
                      <small>
                        {step.why} {step.effect}
                      </small>
                    </div>
                    <Pill tone="policy">{step.version}</Pill>
                  </div>
                ))}
              </div>
            </section>
            <section className="drawer-section">
              <div className="section-title">
                Shadow comparison <span>Candidate never overrides authoritative output</span>
              </div>
              {(() => {
                const candidateAction = detail.shadow_evaluation.candidate.steps.find(
                  (step) => step.component === "Recommendation",
                )?.value;
                const candidateScore = detail.shadow_evaluation.candidate.steps.find(
                  (step) => step.component === "Score components",
                )?.value?.candidate;
                const exceptionCount =
                  detail.shadow_evaluation.candidate.steps.find(
                    (step) => step.component === "Positive exceptions",
                  )?.value?.length || 0;
                return (
                  <>
                    <div className="compare-cards">
                      <div>
                        <span>Authoritative v1</span>
                        <strong>{detail.shadow_evaluation.authoritative_action}</strong>
                        <small>score {detail.risk_score}</small>
                      </div>
                      <div>
                        <span>Candidate v2</span>
                        <strong>{candidateAction}</strong>
                        <small>
                          score {candidateScore} · {exceptionCount} exception match
                          {exceptionCount === 1 ? "" : "es"}
                        </small>
                      </div>
                    </div>
                    <p className="shadow-state">
                      <Pill
                        tone={
                          candidateAction === detail.shadow_evaluation.authoritative_action
                            ? "approve"
                            : "medium"
                        }
                      >
                        {candidateAction === detail.shadow_evaluation.authoritative_action
                          ? "same route"
                          : "routing disagreement"}
                      </Pill>{" "}
                      Score and exception changes remain inspectable even when routing is unchanged.
                    </p>
                  </>
                );
              })()}
            </section>
            <section className="drawer-section">
              <h3>Human reviewer feedback</h3>
              {!feedbackWritable && (
                <Boundary>
                  Public demo is read-only. Local decisions require a declared reviewer identity;
                  production must supply it from an identity provider.
                </Boundary>
              )}
              <label className="reviewer-identity">
                Reviewer identity
                <input
                  aria-label="Reviewer identity"
                  disabled={!feedbackWritable}
                  placeholder="Local reviewer ID"
                  value={reviewerId}
                  onChange={(event) => {
                    setReviewerId(event.target.value);
                    setSaved(false);
                  }}
                />
              </label>
              <div className="decision-grid" role="radiogroup" aria-label="Reviewer decision">
                {(detail.decision_scope === "risk_prior"
                  ? ["relevant prior", "not relevant", "needs specialist review", "wrong category"]
                  : [
                      "approve",
                      "reject",
                      "escalate",
                      "wrong category",
                      "false positive",
                      "false negative",
                    ]
                ).map((value) => (
                  <button
                    disabled={!feedbackWritable}
                    role="radio"
                    aria-checked={decision === value}
                    aria-pressed={decision === value}
                    className={decision === value ? "selected" : ""}
                    onClick={() => {
                      setDecision(value);
                      setSaved(false);
                    }}
                    key={value}
                  >
                    {value}
                  </button>
                ))}
              </div>
              <textarea
                aria-label="Reviewer note"
                disabled={!feedbackWritable}
                placeholder="Review note (optional)"
                value={notes}
                onChange={(event) => {
                  setNotes(event.target.value);
                  setSaved(false);
                }}
              />
              <button
                disabled={!feedbackWritable || !reviewerId.trim()}
                className="primary"
                onClick={submit}
              >
                {saved
                  ? "Decision saved"
                  : feedbackWritable
                    ? "Save attributed decision"
                    : "Read-only public demo"}
              </button>
              {error && <p className="error-text">{error}</p>}
            </section>
          </>
        )}
      </aside>
    </div>
  );
}

function Overview({ overview, metrics, cases, onSelect, navigate }) {
  return (
    <>
      <PageHeader
        eyebrow="Strategy operations"
        title="Command Center"
        subtitle="Trace public risk priors through deterministic detection, review routing, and controlled iteration."
        updated={overview.last_updated}
      />
      <Boundary>
        Real public records power this page. Curated benchmark and hypothetical strategy assumptions
        are excluded from every KPI below.
      </Boundary>
      <LifecycleStrip navigate={navigate} />
      <SourceStrip sources={overview.sources} />
      <Kpis overview={overview} />
      <div className="two-col">
        <section className="surface chart">
          <div className="section-title">
            Risk category distribution <span>Real public case mix, not platform prevalence</span>
          </div>
          <ResponsiveContainer width="100%" height={245}>
            <PieChart>
              <Pie
                data={metrics.category_distribution}
                dataKey="cases"
                nameKey="risk_category"
                innerRadius={52}
                outerRadius={78}
                cx="31%"
              >
                {metrics.category_distribution.map((_, index) => (
                  <Cell key={index} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend
                layout="vertical"
                align="right"
                verticalAlign="middle"
                formatter={legendLabel}
                wrapperStyle={{ fontSize: 10, lineHeight: "16px", maxWidth: 215 }}
              />
            </PieChart>
          </ResponsiveContainer>
        </section>
        <section className="surface chart">
          <div className="section-title">
            Dated record volume <span>Descriptive trend</span>
          </div>
          <ResponsiveContainer width="100%" height={245}>
            <AreaChart data={metrics.anomalies}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" minTickGap={24} />
              <YAxis />
              <Tooltip />
              <Area dataKey="cases" stroke="#3476bc" fill="#dce8f5" />
            </AreaChart>
          </ResponsiveContainer>
        </section>
      </div>
      <section className="surface queue-preview">
        <div className="section-title">
          Investigation queue{" "}
          <button onClick={() => navigate("queue")}>
            Open full queue <ArrowRight size={15} />
          </button>
        </div>
        <RiskTable cases={cases} onSelect={onSelect} compact />
      </section>
    </>
  );
}

function QueuePage({ categories, onSelect, overview }) {
  const pageSize = 100;
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [source, setSource] = useState("");
  const [severity, setSeverity] = useState("");
  const [language, setLanguage] = useState("");
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    setOffset(0);
  }, [search, category, source, severity, language, action]);
  useEffect(() => {
    const timer = setTimeout(async () => {
      setLoading(true);
      setLoadError("");
      const params = new URLSearchParams({
        search,
        category,
        source,
        severity,
        language,
        action,
        limit: String(pageSize),
        offset: String(offset),
      });
      try {
        const [cases, count] = await Promise.all([
          api(`/cases?${params}`),
          api(`/cases/count?${params}`),
        ]);
        setRows(cases);
        setTotal(count.total);
      } catch (error) {
        setLoadError(error.message);
      } finally {
        setLoading(false);
      }
    }, 180);
    return () => clearTimeout(timer);
  }, [search, category, source, severity, language, action, offset]);
  const shownEnd = Math.min(total, offset + rows.length);
  const metaRecords = overview?.sources?.find((item) => item.key === "meta")?.records || 0;
  return (
    <>
      <PageHeader
        eyebrow="Case detection → decision routing"
        title="Review Queue"
        subtitle="Segment the complete mart and open an inspectable Investigation Desk trace."
      />
      <Boundary tone={metaRecords ? "blue" : "amber"}>
        {metaRecords
          ? "Queue includes authorized public-ad records and complaint priors; source scope determines which decisions are permitted."
          : "Current snapshot is a CFPB complaint-prior backlog. These rows support analyst research prioritization only—never ad enforcement."}
      </Boundary>
      <section className="surface filters">
        <label>
          <MagnifyingGlass size={17} />
          <input
            aria-label="Search cases"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search case text or ID"
          />
        </label>
        <select
          aria-label="Risk category"
          value={category}
          onChange={(event) => setCategory(event.target.value)}
        >
          <option value="">All categories</option>
          {categories.map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
        <select
          aria-label="Data source"
          value={source}
          onChange={(event) => setSource(event.target.value)}
        >
          <option value="">All real sources</option>
          <option>CFPB</option>
          <option>Meta</option>
        </select>
        <select
          aria-label="Priority"
          value={severity}
          onChange={(event) => setSeverity(event.target.value)}
        >
          <option value="">All priorities</option>
          <option>critical</option>
          <option>high</option>
          <option>medium</option>
          <option>low</option>
        </select>
        <select
          aria-label="Language"
          value={language}
          onChange={(event) => setLanguage(event.target.value)}
        >
          <option value="">All languages</option>
          <option value="en">English</option>
          <option value="zh">Mandarin</option>
          <option value="mixed">Mixed</option>
        </select>
        <select
          aria-label="Routing"
          value={action}
          onChange={(event) => setAction(event.target.value)}
        >
          <option value="">All routing</option>
          <option>prioritize for analyst review</option>
          <option>use as risk prior</option>
          <option>approve</option>
          <option>escalate to human review</option>
          <option>soft reject</option>
          <option>hard reject</option>
        </select>
      </section>
      <section className="surface full-table">
        <div className="section-title">
          Prioritized cases{" "}
          <span>
            {loading
              ? "Loading…"
              : `${fmt.format(total ? offset + 1 : 0)}–${fmt.format(shownEnd)} of ${fmt.format(total)} scoped records`}
          </span>
        </div>
        {loadError ? (
          <Empty title="Queue request failed" detail={loadError} />
        ) : (
          <RiskTable cases={rows} onSelect={onSelect} />
        )}
        <div className="pagination">
          <button
            disabled={offset === 0 || loading}
            onClick={() => setOffset((value) => Math.max(0, value - pageSize))}
          >
            Previous
          </button>
          <span>
            Page {Math.floor(offset / pageSize) + 1} of {Math.max(1, Math.ceil(total / pageSize))}
          </span>
          <button
            disabled={shownEnd >= total || loading}
            onClick={() => setOffset((value) => value + pageSize)}
          >
            Next
          </button>
        </div>
      </section>
    </>
  );
}

function EmergingRisksPage() {
  const state = useEndpoint("/emerging-risks", {
    candidates: [],
    novel_ngrams: [],
    category_spikes: [],
    unusual_evidence_combinations: [],
  });
  const data = state.data;
  return (
    <>
      <PageHeader
        eyebrow="Risk discovery"
        title="Emerging Risks"
        subtitle="Turn dated public evidence shifts into analyst candidates—not automatic policy."
      />
      <Boundary>{data?.causality_note || "Descriptive prioritization only."}</Boundary>
      <DataState {...state}>
        <section className="surface catalog">
          <div className="section-title">
            Candidate signals <span>{data?.method}</span>
          </div>
          {data?.candidates.map((row) => (
            <EmergingRiskRow row={row} key={`${row.emerging_signal}-${row.language}`} />
          ))}
        </section>
        <div className="three-col discovery-panels">
          <section className="surface">
            <div className="section-title">New unigrams & bigrams</div>
            {data?.novel_ngrams.length ? (
              data.novel_ngrams.slice(0, 5).map((row) => (
                <div className="mini-row" key={row.term}>
                  <strong>{row.term}</strong>
                  <span>{row.growth_ratio}×</span>
                </div>
              ))
            ) : (
              <Empty
                title="No qualifying n-gram shift"
                detail="The current recent window produced no term above the baseline filter."
              />
            )}
          </section>
          <section className="surface">
            <div className="section-title">Category volume shifts</div>
            {data?.category_spikes.slice(0, 5).map((row) => (
              <div className="mini-row" key={row.risk_category}>
                <strong>{row.risk_category}</strong>
                <span>{row.growth_ratio}×</span>
              </div>
            ))}
          </section>
          <section className="surface">
            <div className="section-title">Unusual evidence pairs</div>
            {data?.unusual_evidence_combinations.length ? (
              data.unusual_evidence_combinations.slice(0, 5).map((row) => (
                <div className="mini-row" key={row.evidence_combination}>
                  <strong>{row.evidence_combination}</strong>
                  <span>{row.recent_count}</span>
                </div>
              ))
            ) : (
              <Empty
                title="No unusual combination"
                detail="No recent evidence pair exceeded its earlier-history count."
              />
            )}
          </section>
        </div>
      </DataState>
    </>
  );
}
function EmergingRiskRow({ row }) {
  const [action, setAction] = useState("investigate");
  return (
    <div className="catalog-row">
      <div>
        <Pill tone="evidence">candidate only</Pill>
        <h3>{row.emerging_signal}</h3>
        <p>
          {row.affected_category} · {row.language} · latest {row.latest_seen}
        </p>
        <small>{short(row.sample_evidence, 180)}</small>
      </div>
      <div className="catalog-stats">
        <span>
          Recent <b>{row.recent_count}</b>
        </span>
        <span>
          Baseline <b>{row.baseline_count}</b>
        </span>
        <span>
          Growth <b>{row.growth_ratio}×</b>
        </span>
        <label className="next-step">
          Next step
          <select
            aria-label={`Next step for ${row.emerging_signal}`}
            value={action}
            onChange={(event) => setAction(event.target.value)}
          >
            <option>investigate</option>
            <option>monitor</option>
            <option>dismiss</option>
            <option value="propose_taxonomy_signal">propose taxonomy signal</option>
          </select>
          <small>session only</small>
        </label>
      </div>
    </div>
  );
}

function PolicyStudioPage() {
  const state = useEndpoint("/policy-studio");
  const [tab, setTab] = useState("taxonomy");
  const tabs = [
    ["taxonomy", "Risk Taxonomy"],
    ["signals", "Signal Library"],
    ["exceptions", "Exception Library"],
    ["policy_packs", "Policy Packs"],
  ];
  const records = state.data?.[tab] || [];
  const moveTab = (event) => {
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    const current = tabs.findIndex((item) => item[0] === tab);
    const next = (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    setTab(tabs[next][0]);
    document.getElementById(`policy-tab-${tabs[next][0]}`)?.focus();
  };
  return (
    <>
      <PageHeader
        eyebrow="Taxonomy → signals → exceptions → reusable packs"
        title="Policy Studio"
        subtitle="Versioned candidate configuration overlay; deterministic_rules_v1 remains the authoritative runtime."
      />
      <Boundary>
        {state.data?.truth_boundary || "Original independent demo configuration."}
      </Boundary>
      <div
        className="subnav"
        role="tablist"
        aria-label="Policy Studio surfaces"
        onKeyDown={moveTab}
      >
        {tabs.map(([key, label]) => (
          <button
            id={`policy-tab-${key}`}
            role="tab"
            aria-controls="policy-panel"
            aria-selected={tab === key}
            tabIndex={tab === key ? 0 : -1}
            className={tab === key ? "active" : ""}
            onClick={() => setTab(key)}
            key={key}
          >
            {label}
          </button>
        ))}
      </div>
      <DataState {...state}>
        <section
          id="policy-panel"
          role="tabpanel"
          aria-labelledby={`policy-tab-${tab}`}
          className="surface catalog"
        >
          <div className="section-title">
            {tabs.find((item) => item[0] === tab)?.[1]}{" "}
            <span>{records.length} versioned records</span>
          </div>
          {records.map((row) => (
            <div
              className="catalog-row"
              key={row.category_id || row.signal_id || row.exception_id || row.policy_pack_id}
            >
              <div>
                <div className="tag-row">
                  <Pill tone={row.severity === "critical" ? "critical" : "policy"}>
                    {row.signal_type || row.status || `level ${row.level}`}
                  </Pill>
                  <Pill>{row.version}</Pill>
                </div>
                <h3>{row.name}</h3>
                <p>{row.description || row.rationale}</p>
                <PolicyDetails row={row} tab={tab} />
              </div>
              <dl>
                <div>
                  <dt>Owner</dt>
                  <dd>{row.owner}</dd>
                </div>
                <div>
                  <dt>Scope</dt>
                  <dd>
                    {(row.languages || row.applicable_languages || []).join(", ") ||
                      "declared in config"}
                  </dd>
                </div>
                <div>
                  <dt>Source</dt>
                  <dd>{row.source || row.data_scope || "original demo taxonomy"}</dd>
                </div>
              </dl>
            </div>
          ))}
        </section>
      </DataState>
    </>
  );
}
function PolicyDetails({ row, tab }) {
  const entries =
    tab === "signals"
      ? [
          ["Expression", row.expression],
          ["Category", row.category_id],
          ["Enabled", row.enabled ? "yes" : "no"],
          ["Verticals", row.verticals],
        ]
      : tab === "exceptions"
        ? [
            ["Matching logic", row.matching_logic],
            ["Related signals", row.related_signal_ids],
            ["Risk reduction", row.risk_reduction],
            ["Never override", row.never_override_categories],
            ["Human review", row.requires_human_review ? "required" : "conditional"],
          ]
        : tab === "policy_packs"
          ? [
              ["Categories", row.included_categories],
              ["Signals", row.included_signals],
              ["Exceptions", row.included_exceptions],
              ["Markets", row.markets],
              ["Verticals", row.verticals],
            ]
          : [
              ["Category ID", row.category_id],
              ["Parent", row.parent_category_id || "root"],
              ["Markets", row.applicable_markets],
              ["Verticals", row.applicable_verticals],
            ];
  return (
    <div className="config-details">
      {entries.map(([label, value]) => (
        <div key={label}>
          <span>{label}</span>
          <strong>
            {Array.isArray(value)
              ? value.join(", ") || "none"
              : typeof value === "object"
                ? JSON.stringify(value)
                : String(value ?? "—")}
          </strong>
        </div>
      ))}
    </div>
  );
}

function StrategyBuilderPage() {
  const state = useEndpoint("/strategies");
  const [risk, setRisk] = useState(0.46);
  const [escalation, setEscalation] = useState(0.5);
  const [capacity, setCapacity] = useState(120);
  const [preview, setPreview] = useState(null);
  const [previewError, setPreviewError] = useState("");
  const [running, setRunning] = useState(false);
  const current = state.data?.active_version;
  const candidate = state.data?.candidate_version;
  const updatePreviewInput = (setter) => (value) => {
    setter(value);
    setPreview(null);
    setPreviewError("");
  };
  const runPreview = async () => {
    setRunning(true);
    setPreviewError("");
    try {
      setPreview(
        await api("/strategy-preview", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            risk_threshold: risk,
            escalation_threshold: escalation,
            reviewer_capacity: capacity,
          }),
        }),
      );
    } catch (error) {
      setPreviewError(error.message);
    } finally {
      setRunning(false);
    }
  };
  const previewGate = preview?.benchmark?.promotion_gate;
  return (
    <>
      <PageHeader
        eyebrow="Policy inputs → operational routing"
        title="Strategy Builder"
        subtitle="Configure candidate behavior while deterministic_rules_v1 remains authoritative."
      />
      <Boundary>
        {state.data?.guardrail || "Candidate strategies run in shadow mode only."}
      </Boundary>
      <DataState {...state}>
        <div className="builder-grid">
          <section className="surface strategy-version">
            <div className="section-title">
              Current Strategy v1 <Pill tone="approve">enforced</Pill>
            </div>
            <h2>{current?.version_id}</h2>
            <p>{current?.change_reason}</p>
            <div className="strategy-scope">
              Owner {current?.owner} · {current?.markets?.join(", ")} ·{" "}
              {current?.languages?.join(", ")} · sources {current?.sources?.join(", ")}
            </div>
            <div className="threshold-grid">
              <Metric label="Risk threshold" value={current?.risk_threshold} />
              <Metric label="Confidence" value={current?.confidence_threshold} />
              <Metric label="Escalation" value={current?.escalation_threshold} />
              <Metric label="Soft reject" value={current?.soft_reject_threshold} />
              <Metric label="Hard reject" value={current?.hard_reject_threshold} />
              <Metric
                label="Human review"
                value={current?.mandatory_human_review ? "mandatory" : "conditional"}
              />
              <Metric label="Capacity" value={current?.reviewer_capacity} />
              <Metric label="Latency guardrail" value={`${current?.latency_guardrail_ms} ms`} />
            </div>
          </section>
          <section className="surface strategy-version candidate">
            <div className="section-title">
              Candidate Strategy v2.1 <Pill tone="medium">shadow</Pill>
            </div>
            <h2>{candidate?.version_id}</h2>
            <p>{candidate?.change_reason}</p>
            <div className="strategy-scope">
              {candidate?.policy_pack_ids?.length} packs · human review{" "}
              {candidate?.mandatory_human_review ? "mandatory" : "conditional"} · soft reject{" "}
              {candidate?.soft_reject_threshold} · rollback {candidate?.rollback_target}
            </div>
            <label>
              Risk threshold <output>{risk.toFixed(2)}</output>
              <input
                aria-label="Candidate risk threshold"
                type="range"
                min="0.2"
                max={escalation}
                step="0.01"
                value={risk}
                onChange={(event) => updatePreviewInput(setRisk)(Number(event.target.value))}
              />
            </label>
            <label>
              Escalation threshold <output>{escalation.toFixed(2)}</output>
              <input
                aria-label="Candidate escalation threshold"
                type="range"
                min={risk}
                max={candidate?.soft_reject_threshold || 0.74}
                step="0.01"
                value={escalation}
                onChange={(event) => updatePreviewInput(setEscalation)(Number(event.target.value))}
              />
            </label>
            <label>
              Reviewer capacity{" "}
              <input
                aria-label="Candidate reviewer capacity"
                type="number"
                min="1"
                value={capacity}
                onChange={(event) => updatePreviewInput(setCapacity)(Number(event.target.value))}
              />
            </label>
            <button className="primary" disabled={running} onClick={runPreview}>
              {running ? "Running shadow preview…" : "Run shadow preview"}
            </button>
            <p className="microcopy">
              Curated scenarios only · no production deployment · promotion and rollback remain
              RBAC-gated
            </p>
            {previewError && <p className="error-text">{previewError}</p>}
          </section>
        </div>
        {preview && (
          <section className="surface preview-result" aria-live="polite">
            <div className="section-title">
              Staged preview result{" "}
              <Pill tone={preview.within_capacity ? "approve" : "medium"}>
                {preview.within_capacity ? "within capacity" : "over capacity"}
              </Pill>
              <Pill tone={previewGate?.status === "eligible_for_review" ? "approve" : "medium"}>
                {previewGate?.status === "eligible_for_review"
                  ? "quality gate ready"
                  : "quality gate hold"}
              </Pill>
              <span>{preview.strategy.version_id}</span>
            </div>
            <Boundary>{preview.label}</Boundary>
            <Boundary tone={previewGate?.status === "eligible_for_review" ? "blue" : "amber"}>
              {previewGate?.decision}
            </Boundary>
            <div className="preview-metrics">
              <Metric label="Scenarios" value={preview.scenario_count} />
              <Metric label="Review volume" value={preview.review_volume} />
              <Metric label="Capacity utilization" value={pct(preview.capacity_utilization)} />
              <Metric label="Routing changes" value={preview.disagreement_count} />
              <Metric label="Routing agreement" value={pct(preview.benchmark.routing_agreement)} />
            </div>
            {preview.sample_disagreements.length ? (
              <div className="feature-table">
                {preview.sample_disagreements.map((row, index) => (
                  <div key={row.scenario_id}>
                    <b>{index + 1}</b>
                    <strong>{row.scenario_id}</strong>
                    <span>
                      {row.current_action} → {row.candidate_action}
                    </span>
                    <Pill tone="medium">shadow</Pill>
                  </div>
                ))}
              </div>
            ) : (
              <p className="microcopy">
                No routing differences from the current strategy at these settings.
              </p>
            )}
          </section>
        )}
        <section className="surface lifecycle">
          <div className="section-title">Controlled lifecycle</div>
          {state.data?.lifecycle_states.map((item, index) => (
            <div key={item}>
              <b>{index + 1}</b>
              <strong>{item}</strong>
              <span>
                {item === "enforced"
                  ? "Requires validated evidence and explicit promotion"
                  : item === "shadow"
                    ? "Records disagreements separately"
                    : "Non-authoritative lifecycle state"}
              </span>
            </div>
          ))}
        </section>
      </DataState>
    </>
  );
}
function Metric({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{typeof value === "number" && value < 1 ? value.toFixed(2) : value}</strong>
    </div>
  );
}

function StrategyEvaluationPage() {
  const state = useEndpoint("/strategy-evaluation");
  const [assumptions, setAssumptions] = useState({
    review_minutes_per_case: 3,
    reviewer_hourly_cost: 35,
    model_cost_per_case: 0.002,
    revenue_value_per_allowed_case: 4,
    harm_cost_per_missed_case: 50,
  });
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const rerun = async () => {
    setRunning(true);
    setRunError("");
    try {
      state.setData(
        await api("/strategy-evaluation", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(assumptions),
        }),
      );
    } catch (error) {
      setRunError(error.message);
    } finally {
      setRunning(false);
    }
  };
  const update = (key, value) =>
    setAssumptions((current) => ({ ...current, [key]: Number(value) }));
  const data = state.data;
  const units = {
    review_minutes_per_case: "minutes / case",
    reviewer_hourly_cost: "USD / hour",
    model_cost_per_case: "USD / case if used",
    revenue_value_per_allowed_case: "USD / allowed case",
    harm_cost_per_missed_case: "USD / missed scenario",
  };
  return (
    <>
      <PageHeader
        eyebrow="Shadow comparison and business guardrails"
        title="Strategy Evaluation"
        subtitle="Compare current and candidate routing against isolated curated labels."
      />
      <Boundary tone="amber">
        {data?.assumption_label ||
          "Illustrative scenario assumptions, not observed business values."}
      </Boundary>
      <DataState {...state}>
        <section className="surface assumption-panel">
          <div className="section-title">
            Editable assumptions <span>Used only for hypothetical tradeoff simulation</span>
          </div>
          {Object.entries(assumptions).map(([key, value]) => (
            <label key={key}>
              {key.replaceAll("_", " ")}
              <input
                aria-label={key.replaceAll("_", " ")}
                type="number"
                min="0"
                step="0.001"
                value={value}
                onChange={(event) => update(key, event.target.value)}
              />
              <small>{units[key]}</small>
            </label>
          ))}
          <button className="primary" disabled={running} onClick={rerun}>
            {running ? "Evaluating…" : "Re-run comparison"}
          </button>
          {runError && (
            <p className="error-text" role="alert">
              {runError}
            </p>
          )}
        </section>
        <div className="compare-strategies">
          {[
            ["Current v1", data?.current],
            ["Candidate v2", data?.candidate],
          ].map(([label, row]) => (
            <section className="surface" key={label}>
              <div className="section-title">
                {label}
                <Pill tone={label.includes("Current") ? "approve" : "medium"}>{row?.status}</Pill>
              </div>
              <div className="eval-grid">
                <Metric label="Review volume" value={row?.review_queue_volume} />
                <Metric label="Reviewer utilization" value={pct(row?.reviewer_utilization)} />
                <Metric label="Handling time" value={`${row?.estimated_handling_minutes} min`} />
                <Metric label="SLA pressure" value={row?.estimated_sla_pressure} />
                <Metric label="Review cost" value={money.format(row?.estimated_review_cost || 0)} />
                <Metric
                  label="Actual model cost"
                  value={money.format(row?.estimated_model_cost || 0)}
                />
                <Metric
                  label="Model cost if applied"
                  value={money.format(row?.illustrative_model_cost_if_applied || 0)}
                />
                <Metric
                  label="Revenue at risk"
                  value={money.format(row?.illustrative_revenue_at_risk || 0)}
                />
                <Metric label="Missed-risk scenarios" value={row?.benchmark_missed_risk_cases} />
                <Metric
                  label="Illustrative harm cost"
                  value={money.format(row?.illustrative_harm_cost || 0)}
                />
                <Metric
                  label="False-positive exposure"
                  value={pct(row?.benchmark_false_positive_exposure)}
                />
                <Metric label="Routing agreement" value={pct(row?.benchmark_routing_agreement)} />
              </div>
            </section>
          ))}
        </div>
        <section className="surface sensitivity">
          <div className="section-title">
            Threshold sensitivity{" "}
            <span>Curated benchmark only · blue review volume · red missed-risk scenarios</span>
          </div>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={data?.threshold_sensitivity}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="threshold" />
              <YAxis />
              <Tooltip />
              <Legend />
              <Bar name="Review volume" dataKey="review_volume" fill="#3476bc" />
              <Bar name="Missed-risk scenarios" dataKey="missed_risk_scenarios" fill="#c9454e" />
            </BarChart>
          </ResponsiveContainer>
        </section>
      </DataState>
    </>
  );
}

function AdvertiserIntegrityPage() {
  const state = useEndpoint("/advertiser-integrity", {
    real_public_profiles: [],
    curated_benchmark_profiles: [],
  });
  return (
    <>
      <PageHeader
        eyebrow="Content → campaign → advertiser → network"
        title="Advertiser Integrity"
        subtitle="Keep observed public creatives separate from hypothetical repeated-pattern scenarios."
      />
      <Boundary>{state.data?.truth_boundary}</Boundary>
      <div className="layer-strip">
        {state.data?.layers?.map((layer) => (
          <span key={layer}>{layer}</span>
        ))}
      </div>
      <DataState {...state}>
        <section className="surface catalog">
          <div className="section-title">
            Authorized public-ad profiles{" "}
            <span>Only populated after authorized Meta ingestion</span>
          </div>
          {state.data?.real_public_profiles.length ? (
            state.data.real_public_profiles.map((row) => (
              <AdvertiserRow row={row} key={row.advertiser_id} />
            ))
          ) : (
            <Empty
              title="No authorized public-ad profiles"
              detail="The current public snapshot contains no Meta Ad Library creatives; no advertisers are invented."
            />
          )}
        </section>
        <section className="surface catalog benchmark-section">
          <div className="section-title">
            Curated benchmark advertisers <Pill tone="medium">not real companies</Pill>
          </div>
          {state.data?.curated_benchmark_profiles.map((row) => (
            <AdvertiserRow row={row} key={row.advertiser_id} />
          ))}
        </section>
      </DataState>
    </>
  );
}
function AdvertiserRow({ row }) {
  return (
    <div className="catalog-row advertiser-row">
      <div>
        <Pill tone={row.data_scope === "curated_benchmark" ? "medium" : "meta"}>
          {row.data_scope}
        </Pill>
        <h3>{row.display_name}</h3>
        <p>{row.recommended_analyst_action}</p>
        <div className="config-details">
          <div>
            <span>Maturity</span>
            <strong>{row.scenario_maturity || "unavailable"}</strong>
          </div>
          <div>
            <span>Repeated categories</span>
            <strong>{row.repeated_risk_categories?.join(", ") || "none observed"}</strong>
          </div>
          <div>
            <span>Off-platform signals</span>
            <strong>{row.off_platform_contact_signals ?? "unavailable"}</strong>
          </div>
          <div>
            <span>Creative clusters</span>
            <strong>{row.similar_creative_clusters ?? "unavailable"}</strong>
          </div>
          <div>
            <span>Velocity</span>
            <strong>{row.velocity_signals || "unavailable"}</strong>
          </div>
          <div>
            <span>Appeal / reversal</span>
            <strong>{row.appeal_or_reversal_status || "unavailable"}</strong>
          </div>
        </div>
      </div>
      <div className="catalog-stats">
        <span>
          Scenarios / creatives <b>{row.total_creatives}</b>
        </span>
        <span>
          Review-routing rate <b>{pct(row.escalation_rate)}</b>
        </span>
        <span>
          Risk <b>{row.integrity_risk_level}</b>
        </span>
      </div>
    </div>
  );
}

function BenchmarkLabPage() {
  const state = useEndpoint("/benchmark-lab?include_results=true");
  const data = state.data;
  const metrics = data
    ? [
        ["Category agreement", data.category_agreement],
        ["Expected-term coverage", data.evidence_coverage],
        ["Routing agreement", data.routing_agreement],
        ["Exception application", data.exception_handling_agreement],
        ["Mandarin expected-term coverage", data.mandarin_variant_coverage],
        ["Exception routing agreement", data.false_positive_scenario_agreement],
      ]
    : [];
  const failures = (data?.results || []).filter(
    (row) => !row.category_agreement || !row.routing_agreement || !row.evidence_agreement,
  );
  return (
    <>
      <PageHeader
        eyebrow="Controlled evaluation"
        title="Curated Scenario Benchmark Lab"
        subtitle="60 labeled scenarios test deterministic behavior without contaminating real-public KPIs."
      />
      <Boundary tone="amber">
        Curated evaluation scenarios — not production records or observed platform ads.
      </Boundary>
      <DataState {...state}>
        <section className="surface benchmark-compare">
          <div className="section-title">
            Frozen v1 → remediated shadow v2.1 <span>Same 60 scenarios · no label changes</span>
          </div>
          <div>
            <span>Category</span>
            <strong>
              {pct(data?.baseline?.category_agreement)} → {pct(data?.category_agreement)}
            </strong>
          </div>
          <div>
            <span>Routing</span>
            <strong>
              {pct(data?.baseline?.routing_agreement)} → {pct(data?.routing_agreement)}
            </strong>
          </div>
          <div>
            <span>Exception routing</span>
            <strong>
              {pct(data?.baseline?.false_positive_scenario_agreement)} →{" "}
              {pct(data?.false_positive_scenario_agreement)}
            </strong>
          </div>
        </section>
        <section className="surface benchmark-summary">
          <div className="section-title">
            Scenario composition <span>Author-curated expected labels and rationales</span>
          </div>
          {[
            ["English", 15],
            ["Mandarin", 15],
            ["Mixed & evasion", 10],
            ["Positive exception", 10],
            ["Advertiser behavior", 10],
          ].map(([label, value]) => (
            <Metric key={label} label={label} value={value} />
          ))}
        </section>
        <section className="benchmark-metrics">
          {metrics.map(([label, value]) => (
            <div className="surface" key={label}>
              <span>{label}</span>
              <strong>{pct(value)}</strong>
              <small>Benchmark agreement · {data.strategy_version}</small>
            </div>
          ))}
        </section>
        <Boundary tone={data?.promotion_gate?.status === "eligible_for_review" ? "blue" : "amber"}>
          {data?.promotion_gate?.decision} Production authorization is evaluated separately.
        </Boundary>
        <section className="surface remediation">
          <div className="section-title">
            Remaining disagreement plan{" "}
            <span>Failure attribution → accountable owner → next test</span>
          </div>
          <div className="remediation-grid">
            {data?.failure_buckets?.map((item) => (
              <article key={item.key}>
                <div>
                  <span>{item.label}</span>
                  <strong>{item.count}</strong>
                </div>
                <p>{item.next_step}</p>
                <small>Owner · {item.owner}</small>
              </article>
            ))}
          </div>
        </section>
        <section className="surface failure-analysis">
          <div className="section-title">
            Disagreement analysis <span>{failures.length} scenarios require inspection</span>
          </div>
          {failures.slice(0, 8).map((row) => (
            <div className="failure-row" key={row.scenario_id}>
              <strong>{row.scenario_id}</strong>
              <span>
                category{" "}
                {row.category_agreement
                  ? "match"
                  : `${row.evaluation.category} ≠ ${row.expected_category}`}
              </span>
              <span>evidence {row.evidence_agreement ? "complete" : "partial"}</span>
              <span>
                routing{" "}
                {row.routing_agreement
                  ? `${row.evaluation.recommended_action} = ${row.expected_routing}`
                  : `${row.evaluation.recommended_action} ≠ ${row.expected_routing}`}
              </span>
            </div>
          ))}
        </section>
        <Boundary>
          These metrics describe agreement with curated labels only. They are not production
          precision, recall, accuracy, false-positive rate, or false-negative rate.
        </Boundary>
        <HoldoutPanel />
        <RuleVsLlmPanel />
      </DataState>
    </>
  );
}

function LaunchReadinessPage() {
  const readiness = useEndpoint("/launch-readiness");
  const mandarin = useEndpoint("/mandarin");
  const observed = (value) =>
    value == null
      ? "not available"
      : typeof value === "boolean"
        ? value
          ? "yes"
          : "no"
        : String(value);
  return (
    <>
      <PageHeader
        eyebrow="Fail-closed production controls"
        title="Launch Readiness"
        subtitle="Separate benchmark improvement from the authority, labels, identity, SLA, and approvals required to enforce."
      />
      <DataState {...readiness}>
        <Boundary
          tone={readiness.data?.status === "eligible_for_controlled_promotion" ? "blue" : "amber"}
        >
          {readiness.data?.decision} Passing the curated benchmark does not bypass production
          controls.
        </Boundary>
        <section className="surface readiness-gates">
          <div className="section-title">
            Promotion gate{" "}
            <span>
              {readiness.data?.candidate_version} · rollback {readiness.data?.rollback_target}
            </span>
          </div>
          {readiness.data?.checks?.map((item) => (
            <div key={item.key}>
              <Pill tone={item.passed ? "approve" : "medium"}>{item.passed ? "PASS" : "HOLD"}</Pill>
              <strong>{item.key.replaceAll("_", " ")}</strong>
              <span>Observed {observed(item.observed)}</span>
              <span>Required {item.required}</span>
              <small>{item.owner}</small>
            </div>
          ))}
        </section>
        <section className="readiness-controls">
          <article className="surface">
            <ShieldCheck size={22} />
            <strong>RBAC</strong>
            <p>
              Default deny across reviewer, queue manager, policy owner, release manager, and
              auditor roles.
            </p>
          </article>
          <article className="surface">
            <UserFocus size={22} />
            <strong>Independent labels</strong>
            <p>
              Two distinct reviewers stay blind until both submit; disagreements require
              adjudication.
            </p>
          </article>
          <article className="surface">
            <Clock size={22} />
            <strong>SLA monitoring</strong>
            <p>
              Tracks open, overdue, due-soon, and completed-on-time assignments from persisted
              timestamps.
            </p>
          </article>
          <article className="surface">
            <Strategy size={22} />
            <strong>Promotion & rollback</strong>
            <p>
              Release-manager execution, explicit reason, rollback target, and append-only audit
              events.
            </p>
          </article>
        </section>
        <section className="surface public-evidence-inline">
          <div className="section-title">
            External evidence now loaded <span>Useful validation · not a gate bypass</span>
          </div>
          <Metric
            label="Real public ads"
            value={readiness.data?.public_evidence?.real_ad_records}
          />
          <Metric
            label="Independent annotators"
            value={readiness.data?.public_evidence?.independent_annotators}
          />
          <div>
            <Pill tone="approve">LOADED</Pill>
            <strong>{readiness.data?.public_evidence?.label_scope}</strong>
            <p>{readiness.data?.public_evidence?.why}</p>
          </div>
        </section>
        <Boundary tone="amber">
          Public ad-perception evidence is now loaded, but authorized platform ads, internal
          enforcement truth, organization-verified identities, reviewer decision SLA history, and
          policy approval are still absent. Those production gates correctly remain HOLD.
        </Boundary>
      </DataState>
      <DataState {...mandarin}>
        <section className="surface capability-matrix">
          <div className="section-title">
            Mandarin and modality coverage{" "}
            <span>Bounded proof, not a general understanding claim</span>
          </div>
          {mandarin.data?.tested_coverage?.map((item) => (
            <div key={item.capability}>
              <strong>{item.capability}</strong>
              <Pill
                tone={
                  item.status === "tested"
                    ? "approve"
                    : item.status === "adapter ready"
                      ? "policy"
                      : "medium"
                }
              >
                {item.status}
              </Pill>
              <span>{item.scope}</span>
            </div>
          ))}
        </section>
      </DataState>
    </>
  );
}

function PublicEvidencePage() {
  const state = useEndpoint("/public-evidence");
  const data = state.data;
  const uw = data?.uw_summary;
  const availability = data?.availability_monitoring;
  const answerRows = [
    [
      "Real public ads",
      data?.answer?.real_public_ads,
      "UW research ads are loaded; TikTok requires approved API access.",
    ],
    [
      "Independent labels",
      data?.answer?.independent_public_labels,
      "Useful external validation, not enforcement ground truth.",
    ],
    [
      "Formal identity",
      data?.answer?.formal_identity,
      "Production reviewers must authenticate through the deploying organization.",
    ],
    [
      "Production SLA",
      data?.answer?.production_sla,
      "Reachability and reviewer-decision SLA remain separate measurements.",
    ],
  ];
  return (
    <>
      <PageHeader
        eyebrow="Public evidence → bounded operational proof"
        title="External Validation Registry"
        subtitle="Use real public records wherever defensible, and refuse substitutions that would corrupt an enforcement claim."
      />
      <DataState {...state}>
        <Boundary>
          {uw?.ad_records} real web ads and {fmt.format(uw?.rating_observations || 0)} human rating
          observations are loaded as aggregate external evidence. No source media or participant
          comments are republished.
        </Boundary>
        <section className="evidence-answer-grid">
          {answerRows.map(([label, answer, detail]) => (
            <article className="surface" key={label}>
              <span>{label}</span>
              <strong>{answer}</strong>
              <p>{detail}</p>
            </article>
          ))}
        </section>
        <section className="surface evidence-sources">
          <div className="section-title">
            Source registry <span>Access status and label meaning travel with every source</span>
          </div>
          {data?.sources?.map((source) => (
            <div key={source.key}>
              <Pill
                tone={
                  source.status.includes("loaded") || source.status.includes("configured")
                    ? "approve"
                    : "medium"
                }
              >
                {source.status.includes("loaded")
                  ? "LOADED"
                  : source.status.includes("configured")
                    ? "CONFIGURED"
                    : "APPROVAL REQUIRED"}
              </Pill>
              <div>
                <strong>{source.name}</strong>
                <span>
                  {fmt.format(source.records || 0)} records · {source.label_scope}
                </span>
                <p>{source.truth_boundary}</p>
              </div>
              <a href={source.source_url} target="_blank" rel="noreferrer">
                Official source <ArrowRight size={14} />
              </a>
            </div>
          ))}
        </section>
        <section className="public-proof-grid">
          <article className="surface">
            <div className="section-title">
              Independent perception evidence <span>UW CHI 2021</span>
            </div>
            <div className="proof-kpis">
              <Metric label="Ads" value={fmt.format(uw?.ad_records || 0)} />
              <Metric label="Annotators" value={fmt.format(uw?.reported_unique_annotators || 0)} />
              <Metric label="Ratings" value={fmt.format(uw?.rating_observations || 0)} />
              <Metric
                label="Mean rating"
                value={`${Number(uw?.mean_overall_rating_1_to_7 || 0).toFixed(2)} / 7`}
              />
            </div>
            <div className="opinion-table">
              {Object.entries(uw?.opinion_label_summary || {}).map(([label, row]) => (
                <div key={label}>
                  <strong>{label}</strong>
                  <span>{pct(row.mean_annotator_share)} mean annotator share</span>
                  <b>{row.ads_with_majority_label}</b>
                  <small>majority-labeled ads</small>
                </div>
              ))}
            </div>
          </article>
          <article className="surface operational-proof">
            <div className="section-title">
              Operational evidence <span>Measured, not borrowed</span>
            </div>
            <div>
              <Pill tone={availability?.reporting_eligible ? "approve" : "medium"}>
                {availability?.reporting_eligible ? "REPORTABLE" : "EARLY"}
              </Pill>
              <strong>{availability?.observation_count || 0} external probes</strong>
              <p>
                {availability?.observed_availability == null
                  ? "The scheduled monitor is ready; no availability percentage is claimed before a real observation."
                  : `${pct(availability.observed_availability)} observed reachability. ${availability.claim_boundary}`}
              </p>
            </div>
            <div>
              <Pill tone="medium">IDENTITY</Pill>
              <strong>{data?.identity_provider?.status.replaceAll("_", " ")}</strong>
              <p>{data?.identity_provider?.reason}</p>
            </div>
            <Boundary tone="amber">
              A public identity dataset cannot prove reviewer identity. An organization-owned OIDC
              provider and real review timestamps remain required before production promotion.
            </Boundary>
          </article>
        </section>
        <section className="surface">
          <div className="section-title">
            Taxonomy alignment{" "}
            <span>Independent human perception vs. prioritized risk categories</span>
          </div>
          <Boundary>{uw?.taxonomy_alignment?.method}</Boundary>
          <div className="feature-table">
            {(uw?.perception_by_content_category || []).slice(0, 8).map((row, index) => (
              <div key={row.content_category}>
                <b>{index + 1}</b>
                <strong>{row.content_category}</strong>
                <span>
                  deceptive {pct(row.mean_deceptive_share)} · clickbait{" "}
                  {pct(row.mean_clickbait_share)} · {row.ad_count} ads
                </span>
                <Pill tone={row.mapped_risk_category ? "approve" : "medium"}>
                  {row.mapped_risk_category ? short(row.mapped_risk_category, 26) : "format only"}
                </Pill>
              </div>
            ))}
          </div>
          <Boundary tone="amber">{uw?.taxonomy_alignment?.readout}</Boundary>
        </section>
        <Boundary>{uw?.truth_boundary}</Boundary>
      </DataState>
    </>
  );
}

function HoldoutPanel() {
  const state = useEndpoint("/holdout-benchmark");
  const d = state.data;
  return (
    <section className="surface">
      <div className="section-title">
        Held-out generalization{" "}
        <span>Authored after v2.1 froze · estimates generalization, not regression</span>
      </div>
      <DataState {...state}>
        <Boundary tone="amber">{d?.label}</Boundary>
        <div className="benchmark-metrics">
          <div className="surface">
            <span>v2.1 category · dev → held-out</span>
            <strong>
              {pct(d?.development_set?.candidate_v2_1?.category_agreement)} →{" "}
              {pct(d?.holdout_set?.candidate_v2_1?.category_agreement)}
            </strong>
            <small>gap {pct(d?.generalization_gap?.category_agreement)}</small>
          </div>
          <div className="surface">
            <span>v2.1 routing · dev → held-out</span>
            <strong>
              {pct(d?.development_set?.candidate_v2_1?.routing_agreement)} →{" "}
              {pct(d?.holdout_set?.candidate_v2_1?.routing_agreement)}
            </strong>
            <small>gap {pct(d?.generalization_gap?.routing_agreement)}</small>
          </div>
          <div className="surface">
            <span>v1 held-out baseline</span>
            <strong>
              {pct(d?.holdout_set?.v1?.category_agreement)} /{" "}
              {pct(d?.holdout_set?.v1?.routing_agreement)}
            </strong>
            <small>category / routing on {d?.holdout_set?.v1?.scenario_count} unseen</small>
          </div>
        </div>
        <Boundary>{d?.readout}</Boundary>
        <section className="surface failure-analysis">
          <div className="section-title">
            Held-out misses <span>{d?.holdout_misses?.length || 0} scenarios</span>
          </div>
          {(d?.holdout_misses || []).slice(0, 8).map((row) => (
            <div className="failure-row" key={row.scenario_id}>
              <strong>{row.scenario_id}</strong>
              <span>
                category{" "}
                {row.category_agreement
                  ? "match"
                  : `${row.observed_category} ≠ ${row.expected_category}`}
              </span>
              <span>
                routing{" "}
                {row.routing_agreement
                  ? "match"
                  : `${row.observed_routing} ≠ ${row.expected_routing}`}
              </span>
            </div>
          ))}
        </section>
      </DataState>
    </section>
  );
}

function RuleVsLlmPanel() {
  const state = useEndpoint("/llm-comparison?limit=5");
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState("");
  const run = async () => {
    setRunning(true);
    setRunError("");
    try {
      state.setData(await api("/llm-comparison/run?limit=5", { method: "POST" }));
    } catch (error) {
      setRunError(error.message);
    } finally {
      setRunning(false);
    }
  };
  const data = state.data;
  return (
    <section className="surface llm-panel">
      <div className="section-title">
        Rule vs optional LLM <span>Deterministic output remains authoritative</span>
      </div>
      <DataState {...state}>
        <Boundary>{data?.note}</Boundary>
        <div className="llm-metrics">
          <Metric
            label="Category agreement"
            value={
              data?.category_agreement_rate == null ? "not run" : pct(data.category_agreement_rate)
            }
          />
          <Metric
            label="Evidence overlap"
            value={
              data?.evidence_overlap_rate == null ? "not run" : pct(data.evidence_overlap_rate)
            }
          />
          <Metric
            label="Routing agreement"
            value={
              data?.routing_agreement_rate == null ? "not run" : pct(data.routing_agreement_rate)
            }
          />
          <Metric
            label="Unsupported evidence"
            value={
              data?.unsupported_evidence_rate == null
                ? "not run"
                : pct(data.unsupported_evidence_rate)
            }
          />
          <Metric
            label="Avg LLM latency"
            value={
              data?.average_llm_latency_ms == null ? "not run" : `${data.average_llm_latency_ms} ms`
            }
          />
          <Metric
            label="Cost"
            value={
              data?.estimated_llm_cost_usd == null
                ? "unavailable"
                : money.format(data.estimated_llm_cost_usd)
            }
          />
          <Metric
            label="Failures"
            value={data?.llm_requested ? (data?.failure_count ?? 0) : "not run"}
          />
        </div>
        {data?.llm_available ? (
          <button className="primary" disabled={running} onClick={run}>
            {running ? "Running authorized comparison…" : "Run authorized LLM comparison"}
          </button>
        ) : (
          <p className="microcopy">
            No API key is configured. No model call is made and no output is fabricated.
          </p>
        )}
        {runError && (
          <p className="error-text" role="alert">
            {runError}
          </p>
        )}
      </DataState>
    </section>
  );
}

function MetricsPage({ metrics }) {
  const operations = useEndpoint("/operational-performance");
  const stages = Object.entries(operations.data?.stages || {});
  const diagnosis = metrics.metric_change_summary || {};
  return (
    <>
      <PageHeader
        eyebrow="Operational monitoring and descriptive attribution"
        title="Metric Diagnosis"
        subtitle="Separate observed public-record composition from test-run system measurements."
      />
      <Boundary>
        Descriptive attribution, not causal inference. No production-scale traffic is claimed.
      </Boundary>
      <section className="surface diagnosis-callout">
        <div>
          <span>Operator readout</span>
          <strong>{diagnosis.operator_readout}</strong>
          <p>{diagnosis.recommended_action}</p>
        </div>
        <dl>
          <div>
            <dt>Recent 90d</dt>
            <dd>{pct(diagnosis.recent_high_priority_rate)}</dd>
          </div>
          <div>
            <dt>Prior 90d</dt>
            <dd>{pct(diagnosis.baseline_high_priority_rate)}</dd>
          </div>
          <div>
            <dt>Primary driver</dt>
            <dd>{diagnosis.primary_driver}</dd>
          </div>
        </dl>
      </section>
      <div className="strategy-brief">
        {metrics.strategy_brief.map((item) => (
          <div className="surface" key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <p>{item.detail}</p>
          </div>
        ))}
      </div>
      <div className="metric-grid">
        <section className="surface wide-chart">
          <div className="section-title">
            Risk volume and z-score <span>Dated public records</span>
          </div>
          <ResponsiveContainer width="100%" height={270}>
            <AreaChart data={metrics.anomalies}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="date" />
              <YAxis />
              <Tooltip />
              <Area dataKey="cases" stroke="#3476bc" fill="#dce8f5" />
              <Area dataKey="z_score" stroke="#c9454e" fill="transparent" />
            </AreaChart>
          </ResponsiveContainer>
        </section>
        <section className="surface">
          <div className="section-title">
            Feature lift <span>Descriptive differentiation</span>
          </div>
          <div className="feature-table">
            {metrics.feature_lift.map((row, index) => (
              <div key={row.term}>
                <b>{index + 1}</b>
                <strong>{row.term}</strong>
                <span>{row.high_risk_cases} high-priority</span>
                <Pill>{row.lift}×</Pill>
              </div>
            ))}
          </div>
        </section>
        <section className="surface wide-chart">
          <div className="section-title">
            Root-cause decomposition <span>Source · category · language · market · evidence</span>
          </div>
          <p className="microcopy">{metrics.root_cause_note}</p>
          <div className="feature-table">
            {(metrics.root_cause_by_dimension || []).slice(0, 10).map((row, index) => (
              <div key={`${row.dimension}-${row.segment}`}>
                <b>{index + 1}</b>
                <strong>
                  {row.dimension}: {row.segment}
                </strong>
                <span>
                  mix {Number(row.composition_shift_contribution).toFixed(3)} · rate{" "}
                  {Number(row.within_segment_rate_contribution).toFixed(3)}
                </span>
                <Pill>{row.recent_cases} recent</Pill>
              </div>
            ))}
          </div>
          <p className="microcopy">
            Advertiser vertical is explicitly unavailable in the current snapshot; market represents
            CFPB state only.
          </p>
        </section>
        <section className="surface">
          <div className="section-title">
            Test-run performance <span>{operations.data?.measurement_scope}</span>
          </div>
          <DataState {...operations}>
            <div className="eval-grid">
              <Metric label="Requests measured" value={operations.data?.request_count} />
              <Metric label="p50 latency" value={`${operations.data?.p50_latency_ms} ms`} />
              <Metric label="p95 latency" value={`${operations.data?.p95_latency_ms} ms`} />
              <Metric label="p99 latency" value={`${operations.data?.p99_latency_ms} ms`} />
              <Metric label="Failures" value={operations.data?.failure_count} />
              <Metric
                label="Throughput"
                value={`${operations.data?.throughput_cases_per_second}/s`}
              />
            </div>
            <div className="feature-table">
              {stages.map(([name, row]) => (
                <div key={name}>
                  <b>·</b>
                  <strong>{name.replaceAll("_", " ")}</strong>
                  <span>p95 {row.p95_latency_ms} ms</span>
                  <Pill>{row.measurement_count} runs</Pill>
                </div>
              ))}
            </div>
          </DataState>
        </section>
      </div>
    </>
  );
}

function FeedbackPage({ evaluation, health }) {
  return (
    <>
      <PageHeader
        eyebrow="Controlled iteration"
        title="Human Feedback"
        subtitle="Reviewer decisions unlock eligible quality metrics without manufacturing labels."
      />
      <Boundary>
        {health.feedback_writable
          ? "Local writable mart: reviewer decisions persist separately from original scores."
          : "Public deployment is read-only. No ephemeral serverless label is presented as durable feedback."}
      </Boundary>
      <section className="surface callout">
        <CheckCircle size={26} />
        <div>
          <strong>{evaluation.labeled_cases || 0} eligible cases labeled</strong>
          <p>{evaluation.label_note}</p>
        </div>
      </section>
      <section className="surface">
        <div className="eval-grid">
          <Metric
            label="Precision"
            value={evaluation.precision == null ? "Awaiting labels" : pct(evaluation.precision)}
          />
          <Metric
            label="Recall"
            value={evaluation.recall == null ? "Awaiting labels" : pct(evaluation.recall)}
          />
          <Metric
            label="F1"
            value={evaluation.f1 == null ? "Awaiting labels" : pct(evaluation.f1)}
          />
          <Metric label="Scored cases" value={evaluation.scored_cases} />
        </div>
      </section>
    </>
  );
}

function ProvenancePage() {
  const state = useEndpoint("/system-provenance", { data_scopes: {}, controls: [] });
  return (
    <>
      <PageHeader
        eyebrow="System and truth boundaries"
        title="System & Data Provenance"
        subtitle="Inspect what every scope can—and cannot—support."
      />
      <DataState {...state}>
        <div className="provenance-layout">
          <section className="surface catalog">
            <div className="section-title">Data scopes</div>
            {Object.entries(state.data?.data_scopes || {}).map(([key, value]) => (
              <div className="catalog-row" key={key}>
                <div>
                  <Pill
                    tone={
                      key.includes("curated") || key.includes("hypothetical") ? "medium" : "approve"
                    }
                  >
                    {key}
                  </Pill>
                  <h3>{key.replaceAll("_", " ")}</h3>
                  <p>{value}</p>
                </div>
              </div>
            ))}
          </section>
          <section className="surface controls">
            <div className="section-title">
              Enforced controls <span>{state.data?.deployment_mode}</span>
            </div>
            {state.data?.controls.map((item) => (
              <div key={item}>
                <CheckCircle size={18} />
                <span>{item}</span>
              </div>
            ))}
          </section>
        </div>
      </DataState>
    </>
  );
}

export function App() {
  const [page, setPage] = useState("overview");
  const [selectedCase, setSelectedCase] = useState(null);
  const [data, setData] = useState({
    health: { feedback_writable: true },
    overview: null,
    metrics: null,
    cases: [],
  });
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const [health, overview, metrics, cases] = await Promise.all([
        api("/health"),
        api("/overview"),
        api("/metrics"),
        api("/cases?limit=8"),
      ]);
      setData({ health, overview, metrics, cases });
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [page]);
  const closeCase = useCallback(() => setSelectedCase(null), []);
  const label = nav.find((item) => item[0] === page)?.[1];
  if (error)
    return (
      <main className="boot-error">
        <WarningCircle size={34} />
        <h1>AdShield needs its analytical mart</h1>
        <p>{error}</p>
      </main>
    );
  if (!data.overview)
    return (
      <main className="boot-error">
        <ShieldCheck size={36} />
        <h1>Loading AdShield AI</h1>
        <p>Connecting product strategy to scoped evidence.</p>
      </main>
    );
  let content;
  if (page === "overview")
    content = <Overview {...data} onSelect={setSelectedCase} navigate={setPage} />;
  else if (page === "queue")
    content = (
      <QueuePage
        categories={data.metrics.category_distribution.map((item) => item.risk_category)}
        overview={data.overview}
        onSelect={setSelectedCase}
      />
    );
  else if (page === "emerging") content = <EmergingRisksPage />;
  else if (page === "advertisers") content = <AdvertiserIntegrityPage />;
  else if (page === "policy") content = <PolicyStudioPage />;
  else if (page === "strategy") content = <StrategyBuilderPage />;
  else if (page === "evaluation") content = <StrategyEvaluationPage />;
  else if (page === "metrics") content = <MetricsPage metrics={data.metrics} />;
  else if (page === "benchmark") content = <BenchmarkLabPage />;
  else if (page === "feedback")
    content = <FeedbackPage evaluation={data.metrics.evaluation || {}} health={data.health} />;
  else if (page === "evidence") content = <PublicEvidencePage />;
  else if (page === "readiness") content = <LaunchReadinessPage />;
  else content = <ProvenancePage />;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <ShieldCheck size={31} weight="duotone" />
          </div>
          <div>
            <strong>AdShield AI</strong>
            <span>
              Commercial Ads
              <br />
              Risk Strategy Platform
            </span>
          </div>
        </div>
        <div className="real-only">
          <i />
          Scoped evidence · explicit provenance
        </div>
        <nav aria-label="Product sections">
          {nav.map(([key, title, Icon]) => (
            <button
              key={key}
              aria-label={title}
              aria-current={page === key ? "page" : undefined}
              title={title}
              className={page === key ? "active" : ""}
              onClick={() => setPage(key)}
            >
              <Icon size={19} />
              <span>{title}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <FlowArrow size={18} />
          <span>
            deterministic_rules_v1
            <br />
            <small>Candidate v2.1 · shadow only</small>
          </span>
        </div>
      </aside>
      <main id="main-content" tabIndex="-1" className="content" aria-label={label}>
        {content}
      </main>
      {selectedCase && (
        <CaseDrawer
          caseId={selectedCase}
          onClose={closeCase}
          onFeedback={load}
          feedbackWritable={data.health.feedback_writable}
        />
      )}
    </div>
  );
}
