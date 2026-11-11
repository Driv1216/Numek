import { useState } from "react";
import {
  ArrowRight,
  ArrowLeft,
  Check,
  FileText,
  ShieldCheck,
  ChevronDown,
  Plus,
  Layers,
  Table2,
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
  exportConfig,
  download,
  type Family,
} from "../../data";
import "./guided.css";
export function Guided() {
  const start = new URLSearchParams(location.search).get("view");
  const [stage, setStage] = useState(start === "new" ? 0 : 4),
    [family, setFamily] = useState<Family>("classification"),
    [target, setTarget] = useState(""),
    [source, setSource] = useState(false),
    [ack, setAck] = useState(false),
    [detail, setDetail] = useState<number | null>(0),
    [record, setRecord] = useState("A019"),
    [tab, setTab] = useState("findings"),
    [method, setMethod] = useState(false),
    [delimiter, setDelimiter] = useState(","),
    [note, setNote] = useState(""),
    [reviews, setReviews] = useState<Record<string, string>>({});
  const r = records.find((x) => x.id === record)!;
  const stages = ["Purpose", "Inputs", "Configure", "Confirm", "Investigate"];
  const reset = () => {
    setStage(0);
    setSource(false);
    setTarget("");
    setAck(false);
    setMethod(false);
  };
  return (
    <div className="guided">
      <header className="g-header">
        <a href="/guided" className="g-brand">
          <span className="g-symbol">N</span>
          <strong>
            NUMEK <small>DataTrust</small>
          </strong>
        </a>
        <span className="g-local">
          <ShieldCheck size={15} /> Local investigation · fixture prototype
        </span>
        <button onClick={reset}>
          <Plus size={16} /> New analysis
        </button>
      </header>
      <nav className="g-stages" aria-label="Investigation stages">
        {stages.map((s, i) => (
          <button
            key={s}
            disabled={i > stage}
            className={stage === i ? "current" : ""}
            onClick={() => {
              setStage(i);
              setMethod(false);
            }}
          >
            <span>
              {i < stage ? <Check size={13} /> : String(i + 1).padStart(2, "0")}
            </span>
            {s}
            {i < 4 && <ArrowRight className="g-stage-arrow" size={16} />}
          </button>
        ))}
      </nav>
      <div className="g-work">
        <main className="g-main" key={stage + String(method)}>
          <div className="g-eyebrow">
            INVESTIGATION /{" "}
            {method ? "METHODOLOGY" : stages[stage].toUpperCase()}{" "}
            <span>01 — GUIDED STUDIO</span>
          </div>
          {method ? (
            <>
              <h1>Understand the evidence.</h1>
              <p className="g-lead">
                A clear boundary around every conclusion.
              </p>
              {principles.map(([title, text]) => (
                <section className="g-method" key={title}>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </section>
              ))}
              <details>
                <summary>
                  Implemented analysis families <ChevronDown size={15} />
                </summary>
                {capabilities.map(([id, name, text]) => (
                  <p key={id}>
                    <strong>
                      {id} · {name}
                    </strong>
                    <br />
                    {text}
                  </p>
                ))}
                <p>
                  M8 audio is deferred. Setup previews here cover classification
                  and M9.
                </p>
              </details>
              <div className="g-actions">
                <a
                  href={fixtureLink(family, "html")}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open existing HTML report ↗
                </a>
                <a href={fixtureLink(family, "json")} download>
                  Download fixture JSON ↓
                </a>
                {family === "connected" && (
                  <a href={fixtureLink(family, "pdf")} download>
                    Download existing PDF ↓
                  </a>
                )}
                <button
                  onClick={() =>
                    download("prototype-guided-review.json", {
                      prototype: true,
                      entries: reviews,
                    })
                  }
                >
                  Export separate review snapshot
                </button>
                <button onClick={() => setMethod(false)}>
                  Return to investigation
                </button>
              </div>
            </>
          ) : stage === 0 ? (
            <>
              <h1>
                What do you want
                <br />
                to understand?
              </h1>
              <p className="g-lead">
                Start with the question. We’ll help you make the declarations
                that matter.
              </p>
              <div className="g-purpose">
                {(["classification", "connected"] as Family[]).map((f, i) => (
                  <button
                    key={f}
                    className={family === f ? "selected" : ""}
                    onClick={() => {
                      setFamily(f);
                      setTarget("");
                      setSource(false);
                      setAck(false);
                    }}
                  >
                    <span>
                      {i === 0 ? <Table2 size={24} /> : <Layers size={24} />}
                    </span>
                    <div>
                      <h3>
                        {f === "classification"
                          ? "Can I rely on these labels?"
                          : "Do the records agree with their sources?"}
                      </h3>
                      <p>
                        {f === "classification"
                          ? "Classification · target balance, repetition and input evidence"
                          : "Connected evidence · explicit relationships and document reconciliation"}
                      </p>
                    </div>
                    <span>
                      {family === f ? (
                        <Check size={19} />
                      ) : (
                        <ArrowRight size={19} />
                      )}
                    </span>
                  </button>
                ))}
              </div>
              <details>
                <summary>Explore other implemented analysis families</summary>
                {capabilities.map(([id, name, text]) => (
                  <p key={id}>
                    <b>
                      {id} / {name}
                    </b>
                    <br />
                    {text}
                  </p>
                ))}
                <p>
                  These families are documented here; the two shared journeys
                  have interactive setup.
                </p>
              </details>
              <button className="g-primary" onClick={() => setStage(1)}>
                Choose inputs <ArrowRight size={17} />
              </button>
            </>
          ) : stage === 1 ? (
            <>
              <h1>Meet your inputs.</h1>
              <p className="g-lead">
                Use a known example to explore the workflow. No files leave your
                computer.
              </p>
              <button className="g-source" onClick={() => setSource(true)}>
                <FileText size={30} />
                <div>
                  <h3>
                    {family === "classification"
                      ? "Adult · classification fixture"
                      : "Financial evidence · synthetic fixture"}
                  </h3>
                  <p>
                    {family === "classification"
                      ? "48,842 rows / 15 columns / UCI Adult"
                      : "records.csv / 20 records / 21 native PDFs"}
                  </p>
                </div>
                <span>{source ? <Check /> : "Use fixture →"}</span>
              </button>
              {source && (
                <>
                  <p className="g-small">
                    Fixture preview ·{" "}
                    {family === "classification"
                      ? "5 displayed rows; full stored evidence is separate"
                      : "5 of 20 records; revenue in INR"}
                  </p>
                  <div className="g-table">
                    <table>
                      <thead>
                        <tr>
                          {(family === "classification"
                            ? [
                                "age",
                                "education",
                                "hours_per_week",
                                "annual_income_over_50k",
                              ]
                            : ["id", "entity", "period", "revenue"]
                          ).map((x) => (
                            <th key={x}>{x}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {(family === "classification"
                          ? c.preview
                          : records
                              .slice(0, 5)
                              .map((r) => ({
                                id: r.id,
                                entity: r.entity,
                                period: r.period,
                                revenue: r.revenue,
                              }))
                        ).map((row, i) => (
                          <tr key={i}>
                            {Object.values(row).map((v, j) => (
                              <td key={j}>{v}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <label className="g-field">
                    CSV delimiter
                    <select
                      value={delimiter}
                      onChange={(e) => {
                        setDelimiter(e.target.value);
                        setAck(false);
                      }}
                    >
                      <option value=",">Comma (,)</option>
                      <option value=";">Semicolon (;)</option>
                    </select>
                  </label>
                  {delimiter !== "," && (
                    <p role="alert">
                      This fixture uses commas. Restore comma parsing to
                      continue; no parser runs here.
                    </p>
                  )}
                </>
              )}
              <div className="g-actions">
                <button onClick={() => setStage(0)}>
                  <ArrowLeft size={15} /> Back
                </button>
                <button
                  className="g-primary"
                  disabled={!source || delimiter !== ","}
                  onClick={() => setStage(2)}
                >
                  Configure analysis <ArrowRight size={16} />
                </button>
              </div>
            </>
          ) : stage === 2 ? (
            <>
              <h1>Make the meaning explicit.</h1>
              <p className="g-lead">
                Declarations are part of the evidence. Nothing is selected by
                inference.
              </p>
              {family === "classification" ? (
                <>
                  <label className="g-field">
                    What is the outcome column?
                    <select
                      value={target}
                      onChange={(e) => {
                        setTarget(e.target.value);
                        setAck(false);
                      }}
                    >
                      <option value="">Choose a target</option>
                      <option value="annual_income_over_50k">
                        annual_income_over_50k — 2 observed classes
                      </option>
                    </select>
                  </label>
                  <div className="g-callout">
                    <b>Why this column?</b>
                    <p>
                      An outcome-word name and two observed categories make it a
                      plausible choice. Only you can declare it as the intended
                      outcome.
                    </p>
                  </div>
                  <p>
                    Remaining columns are inputs. This legacy classification
                    fixture uses expected labels.
                  </p>
                </>
              ) : (
                <>
                  <div className="g-mapping">
                    <span>records.entity + period</span>
                    <ArrowRight />
                    <span>documents.entity + period</span>
                  </div>
                  <label className="g-field">
                    Comparison method
                    <select>
                      <option>decimal · declared exact equality</option>
                    </select>
                  </label>
                  <div className="g-facts">
                    <span>
                      Field <b>revenue</b>
                    </span>
                    <span>
                      Unit <b>INR</b>
                    </span>
                    <span>
                      Tolerance <b>0</b>
                    </span>
                    <span>
                      Relationship <b>one_to_many</b>
                    </span>
                  </div>
                  <details>
                    <summary>View source and recipe declarations</summary>
                    <pre>
                      {JSON.stringify(
                        {
                          layout: "finance",
                          kind: "table_field",
                          headers: ["Metric", "Period", "Value"],
                          row_label: "Revenue",
                          period_selector: "period",
                          strategy: "lines",
                          cutoff: "2026-01-01T00:00:00Z",
                          availability: "2025-12-01T00:00:00Z",
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </>
              )}
              <label className="g-field">
                Purpose (optional)
                <textarea
                  value={note}
                  onChange={(e) => {
                    setNote(e.target.value);
                    setAck(false);
                  }}
                  placeholder="What decision will this investigation support?"
                />
              </label>
              <div className="g-actions">
                <button onClick={() => setStage(1)}>Back to inputs</button>
                <button
                  className="g-primary"
                  disabled={family === "classification" && !target}
                  onClick={() => setStage(3)}
                >
                  Review declarations <ArrowRight size={16} />
                </button>
              </div>
            </>
          ) : stage === 3 ? (
            <>
              <h1>One last look.</h1>
              <p className="g-lead">
                Confirm the source, meaning and limits before inspecting the
                stored example.
              </p>
              <div className="g-confirm">
                <h3>
                  {family === "classification"
                    ? "Adult classification"
                    : "Connected financial evidence"}
                </h3>
                <dl>
                  <dt>Source</dt>
                  <dd>
                    {family === "classification"
                      ? "Public UCI fixture · 48,842 rows"
                      : "Synthetic fixture · 20 records / 21 PDFs"}
                  </dd>
                  <dt>Task</dt>
                  <dd>
                    {family === "classification"
                      ? `Classification / ${target}`
                      : "Decimal reconciliation / revenue / INR"}
                  </dd>
                  <dt>Execution</dt>
                  <dd>Simulation only. Existing results will be displayed.</dd>
                  <dt>Purpose</dt>
                  <dd>{note || "Not supplied"}</dd>
                </dl>
              </div>
              <label className="g-check">
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                />{" "}
                I understand that this opens stored fixture evidence and does
                not run an analysis.
              </label>
              <div className="g-actions">
                <button
                  onClick={() => {
                    setStage(2);
                    setAck(false);
                  }}
                >
                  Edit configuration
                </button>
                <button
                  onClick={() =>
                    exportConfig(family, target, { purpose: note, delimiter })
                  }
                >
                  Export prototype configuration
                </button>
                <button
                  className="g-primary"
                  disabled={!ack}
                  onClick={() => {
                    setStage(4);
                    setTab("findings");
                  }}
                >
                  Open fixture investigation <ArrowRight size={16} />
                </button>
              </div>
            </>
          ) : (
            <>
              <h1>
                {family === "classification"
                  ? "A clearer picture of Adult."
                  : "Trace the two disagreements."}
              </h1>
              <p className="g-lead">
                {family === "classification"
                  ? "A completed classification example. Start with what deserves your attention."
                  : "20 records meet 21 source documents. Agreement is a comparison result, not proof of truth."}
              </p>
              <div className="g-result-strip">
                {family === "classification" ? (
                  <>
                    <div>
                      <b>
                        69<span>/100</span>
                      </b>
                      <p>Elevated · classification policy</p>
                    </div>
                    <div>
                      <b>48,842</b>
                      <p>rows · 15 columns</p>
                    </div>
                    <div>
                      <b>4</b>
                      <p>prioritized findings</p>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <b>18</b>
                      <p>agreements</p>
                    </div>
                    <div>
                      <b>1</b>
                      <p>discrepancy</p>
                    </div>
                    <div>
                      <b>1</b>
                      <p>conflict</p>
                    </div>
                  </>
                )}
              </div>
              <nav className="g-tabs">
                <button
                  className={tab === "findings" ? "active" : ""}
                  onClick={() => setTab("findings")}
                >
                  Findings & evidence
                </button>
                <button
                  className={tab === "coverage" ? "active" : ""}
                  onClick={() => setTab("coverage")}
                >
                  Coverage & interpretation
                </button>
                <button
                  onClick={() =>
                    setFamily(
                      family === "classification"
                        ? "connected"
                        : "classification",
                    )
                  }
                >
                  Open{" "}
                  {family === "classification" ? "connected" : "classification"}{" "}
                  example ↗
                </button>
              </nav>
              {tab === "coverage" ? (
                <div className="g-method">
                  <h3>
                    {family === "classification"
                      ? "Explain the score path"
                      : "Read the coverage ledger"}
                  </h3>
                  <p>
                    {family === "classification"
                      ? "Evidence-score mean: 89.15. Target balance is 47.86; the critical-sub-score guardrail caps the final score at 69. Label-conflict evidence does not change the score."
                      : "Decimal rule: 20 records, 21 candidate occurrences, 0 incomplete records, 20 retained investigations. Native PDF extraction completed; layout assurance is not established."}
                  </p>
                  <p>
                    Full population facts and bounded optional searches are
                    different. Source names and optional semantic judgments do
                    not establish correctness.
                  </p>
                </div>
              ) : family === "classification" ? (
                <div className="g-findings">
                  {findings.map((f, i) => (
                    <section key={f.code}>
                      <button
                        onClick={() => setDetail(detail === i ? null : i)}
                        aria-expanded={detail === i}
                      >
                        <span className="g-order">
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <div>
                          <h3>{f.title}</h3>
                          <p>{f.evidence}</p>
                        </div>
                        <ChevronDown size={18} />
                      </button>
                      {detail === i && (
                        <div className="g-detail">
                          <p>{f.finding}</p>
                          <h4>What this means</h4>
                          <p>{f.modeling_impact}</p>
                          <h4>Recommended next step</h4>
                          <p>{f.recommendation}</p>
                          <small>{f.score_effect}</small>
                          {i === 0 && (
                            <div className="g-table">
                              <table>
                                <thead>
                                  <tr>
                                    <th>CSV row</th>
                                    <th>Age</th>
                                    <th>Education</th>
                                    <th>Hours/week</th>
                                    <th>Outcome</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {c.conflict_example.map((x) => (
                                    <tr key={x.row}>
                                      <td>{x.row}</td>
                                      <td>{x.age}</td>
                                      <td>{x.education}</td>
                                      <td>{x.hours_per_week}</td>
                                      <td>{x.annual_income_over_50k}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                              <p className="g-small">
                                Excerpt of one actual feature-identical group;
                                row numbers include the CSV header. All 14
                                recorded features agree.
                              </p>
                            </div>
                          )}
                        </div>
                      )}
                    </section>
                  ))}
                </div>
              ) : (
                <>
                  <label className="g-field">
                    Choose a record
                    <select
                      value={record}
                      onChange={(e) => setRecord(e.target.value)}
                    >
                      {records.map((x) => (
                        <option key={x.id}>{x.id}</option>
                      ))}
                    </select>
                  </label>
                  <div className="g-evidence">
                    <div>
                      <span className={`g-status ${r.status}`}>
                        {statusLabel(r.status)}
                      </span>
                      <h3>{r.id} · Revenue</h3>
                      <p>
                        Structured record: <b>₹{money(r.revenue)}</b>
                        <br />
                        Period: {r.period} · Entity: {r.entity}
                      </p>
                      <p>
                        Declared decimal comparison, tolerance 0.{" "}
                        {r.documents.length} eligible document
                        {r.documents.length > 1 ? "s" : ""}.
                      </p>
                      <label className="g-field">
                        Separate review disposition
                        <select
                          value={reviews[record] || "unreviewed"}
                          onChange={(e) =>
                            setReviews({ ...reviews, [record]: e.target.value })
                          }
                        >
                          <option>unreviewed</option>
                          <option>confirm</option>
                          <option>dismiss</option>
                          <option>unresolved</option>
                        </select>
                      </label>
                      <small>
                        Simulated review · does not change analytical evidence.
                      </small>
                    </div>
                    <div>
                      {r.documents.map((d) => (
                        <article key={d.file}>
                          <FileText size={18} />
                          <h4>{d.file} · page 1</h4>
                          <p>
                            Revenue: <b>₹{money(documentValue(d.text))}</b>
                          </p>
                          <pre>{d.text}</pre>
                          <a
                            href={`/fixtures/${d.file}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Inspect original fixture PDF ↗
                          </a>
                        </article>
                      ))}
                    </div>
                  </div>
                </>
              )}
              <div className="g-actions">
                <button onClick={() => setMethod(true)}>
                  Methodology & exports <ArrowRight size={15} />
                </button>
              </div>
            </>
          )}
        </main>
        <aside className="g-context">
          <span className="g-eyebrow">A LITTLE CONTEXT</span>
          <div className="g-context-line" />
          <h2>
            {stage < 4
              ? "Clarity before complexity."
              : "Evidence before conclusions."}
          </h2>
          <p>
            {stage < 4
              ? "Each stage makes one part of the investigation explicit: your question, your inputs, their meaning and the scope of the analysis."
              : "The finding is the beginning of a review. Follow its evidence, inspect the population and keep the limits in view."}
          </p>
          <div className="g-aside-note">
            <ShieldCheck size={20} />
            <h4>Your sources stay local.</h4>
            <p>
              DataTrust has no cloud upload or account. This design lab uses
              copied public and synthetic examples.
            </p>
          </div>
          <button onClick={() => setMethod(!method)}>
            {method ? "Back to your work" : "How DataTrust interprets evidence"}{" "}
            <ArrowRight size={15} />
          </button>
          <span className="g-margin-index">
            {String(stage + 1).padStart(2, "0")} / 05
          </span>
        </aside>
      </div>
      <footer className="g-footer">
        <span>NUMEK DataTrust / Guided Studio</span>
        <span>Fixture evidence · no analysis executed</span>
      </footer>
    </div>
  );
}
