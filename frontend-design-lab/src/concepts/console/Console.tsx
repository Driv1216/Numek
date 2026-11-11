import { useEffect, useRef, useState } from "react";
import {
  Plus,
  Search,
  Command,
  ChevronRight,
  ArrowDown,
  ArrowUp,
  FileText,
  X,
  PanelRight,
  Download,
  Circle,
  CheckCircle2,
} from "lucide-react";
import {
  classification as c,
  findings,
  records,
  statusLabel,
  money,
  documentValue,
  principles,
  capabilities,
  fixtureLink,
  download,
  exportConfig,
  type Family,
} from "../../data";
import "./console.css";
export function Console() {
  const [family, setFamily] = useState<Family>("classification"),
    [view, setView] = useState(
      new URLSearchParams(location.search).get("view") === "new"
        ? "new"
        : "queue",
    ),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [index, setIndex] = useState(0),
    [inspector, setInspector] = useState(true),
    [command, setCommand] = useState(false),
    [cq, setCq] = useState(""),
    [sort, setSort] = useState("priority"),
    [target, setTarget] = useState(""),
    [source, setSource] = useState(false),
    [ack, setAck] = useState(false),
    [reviews, setReviews] = useState<Record<string, string>>({}),
    [pane, setPane] = useState("evidence");
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const inspectorRef = useRef<HTMLElement>(null);
  const choose = (i: number) => {
    setIndex(i);
    setInspector(true);
    if (window.matchMedia("(max-width:650px)").matches)
      requestAnimationFrame(() =>
        inspectorRef.current?.scrollIntoView({
          behavior: window.matchMedia("(prefers-reduced-motion:reduce)").matches
            ? "instant"
            : "smooth",
          block: "start",
        }),
      );
  };
  const list =
    family === "classification"
      ? findings.filter(
          (f) =>
            (f.title + " " + f.evidence)
              .toLowerCase()
              .includes(query.toLowerCase()) &&
            (filter === "all" || f.severity === filter),
        )
      : records.filter(
          (r) =>
            (r.id + " " + statusLabel(r.status))
              .toLowerCase()
              .includes(query.toLowerCase()) &&
            (filter === "all" || r.status === filter),
        );
  const ordered =
    sort === "name"
      ? [...list].sort((a, b) =>
          ("title" in a ? a.title : a.id).localeCompare(
            "title" in b ? b.title : b.id,
          ),
        )
      : [...list];
  const active = ordered[Math.min(index, Math.max(ordered.length - 1, 0))];
  const selectedKey = active
    ? "code" in active
      ? active.code
      : active.id
    : "";
  useEffect(() => {
    if (command) dialog.current?.showModal();
    else dialog.current?.close();
  }, [command]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const typing =
        e.target instanceof HTMLElement &&
        ["INPUT", "TEXTAREA", "SELECT"].includes(e.target.tagName);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommand((v) => !v);
        return;
      }
      if (e.key === "Escape") {
        setCommand(false);
        return;
      }
      if (typing || command) return;
      if (e.key === "/") {
        e.preventDefault();
        input.current?.focus();
      }
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        setIndex((i) => Math.min(i + 1, Math.max(0, ordered.length - 1)));
      }
      if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        setIndex((i) => Math.max(0, i - 1));
      }
      if (e.key === "Enter") setInspector(true);
      if (e.key === "n") {
        setView("new");
        setSource(false);
        setAck(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [ordered.length, command]);
  const switchFamily = (f: Family) => {
    setFamily(f);
    setIndex(0);
    setFilter("all");
    setQuery("");
    setView("queue");
  };
  const commands = [
    ["New analysis", "n", () => setView("new")],
    ["Open classification example", "", () => switchFamily("classification")],
    ["Open connected evidence", "", () => switchFamily("connected")],
    ["Methodology & export", "", () => setView("method")],
    ["Toggle inspector", "Enter", () => setInspector((v) => !v)],
    [
      "Download separate review snapshot",
      "",
      () =>
        download("prototype-review.json", {
          prototype: true,
          entries: reviews,
        }),
    ],
  ];
  return (
    <div className="console">
      <header className="c-header">
        <a href="/console" className="c-brand">
          <span>◈</span> NUMEK <b>DataTrust</b>
        </a>
        <span className="c-breadcrumb">
          Local workspace <ChevronRight size={12} />{" "}
          {view === "new"
            ? "New analysis"
            : family === "classification"
              ? "Adult classification"
              : "Financial reconciliation"}
        </span>
        <button
          onClick={() => {
            setCommand(true);
            setCq("");
          }}
          className="c-command"
        >
          <Command size={13} /> Commands <kbd>⌘ K</kbd>
        </button>
      </header>
      <nav className="c-nav">
        <button
          className={
            view === "queue" && family === "classification" ? "active" : ""
          }
          onClick={() => switchFamily("classification")}
        >
          Classification <span>4</span>
        </button>
        <button
          className={view === "queue" && family === "connected" ? "active" : ""}
          onClick={() => switchFamily("connected")}
        >
          Connected evidence <span>20</span>
        </button>
        <button
          className={view === "method" ? "active" : ""}
          onClick={() => setView("method")}
        >
          Methodology & exports
        </button>
        <button
          onClick={() => {
            setView("new");
            setSource(false);
            setAck(false);
          }}
        >
          <Plus size={13} /> New analysis
        </button>
      </nav>
      {view === "new" ? (
        <main className="c-intake">
          <div className="c-page-label">NEW / ANALYSIS CONFIGURATION</div>
          <h1>Create an investigation</h1>
          <p>
            Local prototype. Commands configure a preview; opening results loads
            existing fixture evidence.
          </p>
          <div className="c-config-grid">
            <section>
              <h3>01 / Task</h3>
              <label>
                Analysis type
                <select
                  value={family}
                  onChange={(e) => {
                    setFamily(e.target.value as Family);
                    setSource(false);
                    setTarget("");
                    setAck(false);
                  }}
                >
                  <option value="classification">Classification</option>
                  <option value="connected">
                    M9 · Connected records and documents
                  </option>
                </select>
              </label>
              <h3>02 / Inputs</h3>
              <button className="c-load" onClick={() => setSource(true)}>
                <FileText size={16} />
                {family === "classification"
                  ? "Load Adult public fixture"
                  : "Load 20-record synthetic fixture"}{" "}
                {source && <CheckCircle2 size={15} />}
              </button>
              {source && (
                <div className="c-source-preview">
                  <p>
                    {family === "classification"
                      ? "48,842 rows · 15 columns · comma delimiter"
                      : "records.csv + documents.csv · 21 PDFs"}
                  </p>
                  <pre>
                    {family === "classification"
                      ? JSON.stringify(c.preview[0], null, 2)
                      : JSON.stringify(
                          {
                            entity: "A019",
                            period: "FY2025",
                            revenue: "12000000",
                          },
                          null,
                          2,
                        )}
                  </pre>
                </div>
              )}
            </section>
            <section>
              <h3>03 / Declarations</h3>
              {family === "classification" ? (
                <label>
                  Explicit target
                  <select
                    value={target}
                    onChange={(e) => {
                      setTarget(e.target.value);
                      setAck(false);
                    }}
                  >
                    <option value="">Select an outcome</option>
                    <option>annual_income_over_50k</option>
                  </select>
                </label>
              ) : (
                <>
                  <label>
                    Comparison rule
                    <select>
                      <option>revenue · decimal · INR · tolerance 0</option>
                    </select>
                  </label>
                  <label>
                    Relationship
                    <select>
                      <option>entity + period · one_to_many</option>
                    </select>
                  </label>
                  <p className="c-muted">
                    Table recipe: Metric / Period / Value. Native PDF, lines
                    strategy. Optional semantic models are outside this setup
                    preview.
                  </p>
                </>
              )}
              <details>
                <summary>Advanced work scope</summary>
                <p>
                  Source and parsing edits require reconfirmation. Production
                  search limits and omitted details are disclosed independently;
                  this mock does not run a worker.
                </p>
              </details>
              <h3>04 / Confirmation</h3>
              <label className="c-checkbox">
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                />{" "}
                Open stored evidence. No real analysis will run.
              </label>
              <div className="c-config-actions">
                <button
                  disabled={
                    !source || !ack || (family === "classification" && !target)
                  }
                  onClick={() => {
                    setView("queue");
                    setQuery("");
                    setIndex(0);
                    setFilter("all");
                  }}
                >
                  Open fixture result <ChevronRight size={14} />
                </button>
                <button
                  onClick={() => exportConfig(family, target)}
                  disabled={!source || (family === "classification" && !target)}
                >
                  Export configuration
                </button>
              </div>
            </section>
          </div>
        </main>
      ) : view === "method" ? (
        <main className="c-method">
          <div className="c-page-label">REFERENCE / METHODOLOGY</div>
          <h1>Interpretation contract</h1>
          <div className="c-method-grid">
            <div>
              {principles.map(([title, text]) => (
                <section key={title}>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </section>
              ))}
            </div>
            <aside>
              <h3>Completed artifacts</h3>
              <p>
                These links open the repository’s existing fixture artifacts.
                Export never runs analysis.
              </p>
              <a
                href={fixtureLink(family, "html")}
                target="_blank"
                rel="noreferrer"
              >
                <FileText size={14} /> HTML report ↗
              </a>
              <a href={fixtureLink(family, "json")} download>
                <Download size={14} />
                {family === "classification"
                  ? "Validation summary JSON"
                  : "Strict M9 JSON"}
              </a>
              {family === "connected" && (
                <a href={fixtureLink(family, "pdf")} download>
                  <Download size={14} /> PDF report
                </a>
              )}
              <button
                onClick={() =>
                  download("prototype-review.json", {
                    prototype: true,
                    entries: reviews,
                  })
                }
              >
                Export separate review snapshot
              </button>
              <details>
                <summary>Capability map</summary>
                {capabilities.map(([id, title, text]) => (
                  <p key={id}>
                    <b>
                      {id} · {title}
                    </b>
                    <br />
                    {text}
                  </p>
                ))}
                <p>
                  M8 audio deferred. Only classification and M9 have simulated
                  setup in this lab.
                </p>
              </details>
            </aside>
          </div>
        </main>
      ) : (
        <>
          <div className="c-location">
            <div>
              <span className="c-page-label">
                {family === "classification"
                  ? "CLS / UCI ADULT"
                  : "M9 / FINANCIAL EVIDENCE"}
              </span>
              <h1>
                {family === "classification"
                  ? "Finding queue"
                  : "Record investigations"}
              </h1>
            </div>
            <div className="c-facts">
              {family === "classification" ? (
                <>
                  <span>
                    <b>48,842</b> rows
                  </span>
                  <span>
                    <b>69</b> capped score
                  </span>
                  <span>
                    <b>5</b> conflicting groups
                  </span>
                </>
              ) : (
                <>
                  <span>
                    <b>18</b> agreements
                  </span>
                  <span>
                    <b>1</b> discrepancy
                  </span>
                  <span>
                    <b>1</b> conflict
                  </span>
                </>
              )}
            </div>
          </div>
          <div className="c-tools">
            <div className="c-search">
              <Search size={14} />
              <input
                ref={input}
                aria-label="Search findings or records"
                placeholder={
                  family === "classification"
                    ? "Search findings…"
                    : "Search records or status…"
                }
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setIndex(0);
                }}
              />
              <kbd>/</kbd>
            </div>
            <select
              aria-label="Filter queue"
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setIndex(0);
              }}
            >
              <option value="all">
                All {family === "classification" ? "priorities" : "results"}
              </option>
              {(family === "classification"
                ? ["Moderate", "Low"]
                : ["violated", "conflicting_evidence", "satisfied"]
              ).map((x) => (
                <option key={x} value={x}>
                  {family === "classification" ? x : statusLabel(x)}
                </option>
              ))}
            </select>
            <select
              aria-label="Sort queue"
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setIndex(0);
              }}
            >
              <option value="priority">Source / priority order</option>
              <option value="name">Name ascending</option>
            </select>
            <span className="c-count">{ordered.length} results</span>
            <button
              aria-label="Toggle evidence inspector"
              onClick={() => setInspector((v) => !v)}
            >
              <PanelRight size={15} />
            </button>
          </div>
          <div className={`c-body ${inspector ? "" : "no-inspector"}`}>
            <main className="c-queue">
              <div className="c-columns">
                <span>
                  {family === "classification" ? "FINDING" : "RECORD"}
                </span>
                <span>
                  {family === "classification" ? "PRIORITY" : "RESULT"}
                </span>
                <span>
                  {family === "classification" ? "SCOPE" : "DOCUMENTS"}
                </span>
              </div>
              {ordered.length === 0 && (
                <div className="c-empty">
                  <Search />
                  <h3>No matching evidence</h3>
                  <p>Try another query or clear the filter.</p>
                  <button
                    onClick={() => {
                      setQuery("");
                      setFilter("all");
                    }}
                  >
                    Clear search & filter
                  </button>
                </div>
              )}
              {ordered.map((item, i) =>
                "title" in item ? (
                  <button
                    className={`c-row ${index === i ? "selected" : ""}`}
                    key={item.code}
                    onClick={() => choose(i)}
                  >
                    <div>
                      <Circle size={12} />
                      <div>
                        <strong>{item.title}</strong>
                        <p>{item.evidence}</p>
                      </div>
                    </div>
                    <span className={`c-priority ${item.severity}`}>
                      {item.severity}
                    </span>
                    <span>
                      {item.code === "conflicting_target_labels"
                        ? "5 groups"
                        : item.code === "target_imbalance"
                          ? "48,842 labels"
                          : item.code === "numeric_outlier_concentration"
                            ? "1 field"
                            : "1 prompt"}
                    </span>
                  </button>
                ) : (
                  <button
                    className={`c-row ${index === i ? "selected" : ""}`}
                    key={item.id}
                    onClick={() => choose(i)}
                  >
                    <div>
                      <FileText size={13} />
                      <div>
                        <strong>
                          {item.id} <small>Revenue / FY2025</small>
                        </strong>
                        <p>records.csv · entity {item.entity}</p>
                      </div>
                    </div>
                    <span className={`c-priority ${item.status}`}>
                      {statusLabel(item.status)}
                    </span>
                    <span>
                      {item.documents.length}{" "}
                      {item.documents.length === 1 ? "PDF" : "PDFs"}
                    </span>
                  </button>
                ),
              )}
              <div className="c-queue-note">
                <span>Stored fixture evidence</span>
                <p>
                  {family === "classification"
                    ? "The score is capped by the target-balance guardrail. Review-only findings do not imply label errors."
                    : "All 20 declared record comparisons retained. No overall M9 score; optional semantic evidence is separately scoped."}
                </p>
              </div>
            </main>
            {inspector && (
              <aside className="c-inspector" ref={inspectorRef}>
                <div className="c-inspector-head">
                  <span>INSPECTOR</span>
                  <button
                    aria-label="Close inspector"
                    onClick={() => setInspector(false)}
                  >
                    <X size={14} />
                  </button>
                </div>
                {active ? (
                  <>
                    <div className="c-inspector-title">
                      <span className="c-page-label">{selectedKey}</span>
                      <h2>
                        {"title" in active
                          ? active.title
                          : `${active.id} / Revenue`}
                      </h2>
                    </div>
                    <nav className="c-inspector-tabs">
                      {["evidence", "coverage", "review"].map((t) => (
                        <button
                          className={pane === t ? "active" : ""}
                          key={t}
                          onClick={() => setPane(t)}
                        >
                          {t}
                        </button>
                      ))}
                    </nav>
                    <div className="c-inspector-content">
                      {pane === "review" ? (
                        <>
                          <h3>Independent reviewer disposition</h3>
                          <p>This changes the prototype review state only.</p>
                          <label>
                            Disposition
                            <select
                              value={reviews[selectedKey] || "unreviewed"}
                              onChange={(e) =>
                                setReviews({
                                  ...reviews,
                                  [selectedKey]: e.target.value,
                                })
                              }
                            >
                              {[
                                "unreviewed",
                                "confirm",
                                "dismiss",
                                "unresolved",
                              ].map((x) => (
                                <option key={x}>{x}</option>
                              ))}
                            </select>
                          </label>
                          <p className="c-muted">
                            {reviews[selectedKey]
                              ? "Simulated disposition recorded in memory."
                              : "No review recorded."}
                          </p>
                        </>
                      ) : pane === "coverage" ? (
                        <>
                          <h3>Examined scope</h3>
                          <p>
                            {family === "classification"
                              ? "48,842 rows, 15 columns and 48,842 labeled rows. Displayed examples are an excerpt of the stored report."
                              : "20 records / 21 candidate occurrences / 0 incomplete records for the decimal rule. 20 investigations retained; layout assurance remains unestablished."}
                          </p>
                          <p>
                            Presentation omissions and analytical bounds are
                            distinct. Source identity is verified by the
                            production private resolver, not this prototype.
                          </p>
                          <button onClick={() => setView("method")}>
                            Read methodological limits →
                          </button>
                        </>
                      ) : "title" in active ? (
                        <>
                          <h3>Observed evidence</h3>
                          <p>{active.finding}</p>
                          <blockquote>{active.evidence}</blockquote>
                          <h3>Modeling implication</h3>
                          <p>{active.modeling_impact}</p>
                          <h3>Next action</h3>
                          <p>{active.recommendation}</p>
                          <div className="c-score-note">
                            {active.score_effect}
                          </div>
                          {active.code === "conflicting_target_labels" && (
                            <>
                              <h3>One actual group</h3>
                              <pre>
                                {c.conflict_example
                                  .map(
                                    (x) =>
                                      `CSV ${x.row} · age ${x.age} · ${x.annual_income_over_50k}`,
                                  )
                                  .join("\n")}
                              </pre>
                              <p>
                                All 14 recorded features agree. Two opposing
                                labels remain.
                              </p>
                            </>
                          )}
                          {active.code === "target_imbalance" &&
                            Object.entries(c.class_counts).map(([name, n]) => (
                              <div className="c-distribution" key={name}>
                                <span>{name}</span>
                                <b>{n.toLocaleString()}</b>
                                <i
                                  style={{
                                    width: `${(n / c.row_count) * 100}%`,
                                  }}
                                />
                              </div>
                            ))}
                        </>
                      ) : (
                        <>
                          <h3>Original record</h3>
                          <pre>{`id: ${active.id}\nentity: ${active.entity}\nperiod: ${active.period}\nrevenue: ${active.revenue}\ncutoff: ${active.cutoff}`}</pre>
                          <h3>Connected documents</h3>
                          {active.documents.map((d) => (
                            <div className="c-document" key={d.file}>
                              <strong>{d.file} / page 1</strong>
                              <p>
                                Revenue <b>₹{money(documentValue(d.text))}</b>
                              </p>
                              <pre>{d.text}</pre>
                              <a
                                href={`/fixtures/${d.file}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Open original synthetic PDF ↗
                              </a>
                            </div>
                          ))}
                          <div className="c-score-note">
                            Decimal · INR · tolerance 0. Agreement cannot
                            suppress competing eligible evidence.
                          </div>
                        </>
                      )}
                    </div>
                  </>
                ) : (
                  <p className="c-inspector-content">
                    No selection in this filtered population.
                  </p>
                )}
              </aside>
            )}
          </div>
        </>
      )}
      <footer className="c-footer">
        <span>
          <i /> Fixture mode · no execution
        </span>
        <span>
          <kbd>J</kbd>
          <kbd>K</kbd> move <kbd>Enter</kbd> inspect <kbd>/</kbd> search{" "}
          <kbd>N</kbd> new
        </span>
        <span>02 / ANALYST CONSOLE</span>
      </footer>
      <dialog
        ref={dialog}
        className="c-palette"
        onCancel={() => setCommand(false)}
        onClose={() => setCommand(false)}
      >
        <div className="c-palette-input">
          <Search size={18} />
          <input
            autoFocus
            aria-label="Search commands"
            placeholder="Find a command…"
            value={cq}
            onChange={(e) => setCq(e.target.value)}
          />
          <button aria-label="Close commands" onClick={() => setCommand(false)}>
            <X size={16} />
          </button>
        </div>
        <p>WORKSPACE ACTIONS</p>
        {commands
          .filter(([name]) =>
            String(name).toLowerCase().includes(cq.toLowerCase()),
          )
          .map(([name, key, fn]) => (
            <button
              key={String(name)}
              onClick={() => {
                (fn as () => void)();
                setCommand(false);
              }}
            >
              <span>{String(name)}</span>
              <kbd>{String(key) || "↵"}</kbd>
            </button>
          ))}
        <footer>
          <ArrowUp size={12} />
          <ArrowDown size={12} /> Tab to move · Enter to choose · Esc to close
        </footer>
      </dialog>
    </div>
  );
}
