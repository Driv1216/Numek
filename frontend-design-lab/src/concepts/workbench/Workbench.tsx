import { useState } from "react";
import {
  Columns2,
  PanelRightClose,
  PanelRightOpen,
  FileText,
  Table2,
  Plus,
  X,
  ChevronDown,
  ArrowRight,
  Search,
  Maximize2,
  Download,
  SlidersHorizontal,
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
import "./workbench.css";
export function Workbench() {
  const [family, setFamily] = useState<Family>("connected"),
    [screen, setScreen] = useState(
      new URLSearchParams(location.search).get("view") === "new"
        ? "new"
        : "canvas",
    ),
    [id, setId] = useState("A020"),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [inspect, setInspect] = useState(true),
    [split, setSplit] = useState(true),
    [width, setWidth] = useState(43),
    [format, setFormat] = useState("excerpt"),
    [documentIndex, setDocumentIndex] = useState(0),
    [findingIndex, setFindingIndex] = useState(0),
    [target, setTarget] = useState(""),
    [source, setSource] = useState(false),
    [ack, setAck] = useState(false),
    [notes, setNotes] = useState<Record<string, string>>({}),
    [reviews, setReviews] = useState<Record<string, string>>({}),
    [inspectorTab, setInspectorTab] = useState("rule"),
    [showLedger, setShowLedger] = useState(true);
  const r = records.find((x) => x.id === id)!;
  const doc = r.documents[Math.min(documentIndex, r.documents.length - 1)];
  const f = findings[findingIndex];
  const selected = family === "connected" ? id : f.code;
  const filtered = records.filter(
    (x) =>
      x.id.toLowerCase().includes(query.toLowerCase()) &&
      (filter === "all" || x.status === filter),
  );
  function switchTo(value: Family) {
    setFamily(value);
    setScreen("canvas");
    setFormat("excerpt");
  }
  return (
    <div className="workbench">
      <header className="w-menu">
        <a href="/workbench">
          N<span>NUMEK / DataTrust</span>
        </a>
        <span className="w-menu-middle">
          Evidence Workbench <span>· local fixture session</span>
        </span>
        <button
          onClick={() => setScreen(screen === "method" ? "canvas" : "method")}
        >
          Methods & exports
        </button>
        <button
          onClick={() => {
            setScreen("new");
            setSource(false);
            setAck(false);
            setTarget("");
          }}
        >
          <Plus size={14} /> New investigation
        </button>
      </header>
      <nav className="w-project-tabs" aria-label="Open investigations">
        <button
          className={
            screen === "canvas" && family === "connected" ? "active" : ""
          }
          onClick={() => switchTo("connected")}
        >
          <FileText size={14} /> Financial evidence <span>M9</span>
        </button>
        <button
          className={
            screen === "canvas" && family === "classification" ? "active" : ""
          }
          onClick={() => switchTo("classification")}
        >
          <Table2 size={14} /> Adult classification <span>CLS</span>
        </button>
        {screen === "new" && (
          <span className="w-config-tab">
            Untitled configuration{" "}
            <button
              className="w-tab-close"
              aria-label="Close new configuration"
              onClick={() => setScreen("canvas")}
            >
              <X size={12} />
            </button>
          </span>
        )}
      </nav>
      {screen === "new" ? (
        <main className="w-setup">
          <div className="w-setup-title">
            <SlidersHorizontal size={22} />
            <h1>Investigation declarations</h1>
            <small>Simulated configuration · no execution</small>
          </div>
          <div className="w-setup-grid">
            <section>
              <label>
                Task family
                <select
                  value={family}
                  onChange={(e) => {
                    setFamily(e.target.value as Family);
                    setSource(false);
                    setAck(false);
                  }}
                >
                  <option value="connected">M9 · Connected evidence</option>
                  <option value="classification">Classification</option>
                </select>
              </label>
              <h3>Sources</h3>
              <button onClick={() => setSource(true)} className="w-load">
                Attach{" "}
                {family === "connected"
                  ? "synthetic records + PDFs"
                  : "public Adult fixture"}{" "}
                <Plus size={14} />
              </button>
              {source && (
                <div className="w-attached">
                  <FileText size={15} />
                  <span>
                    {family === "connected"
                      ? "records.csv · documents.csv · 21 PDFs"
                      : "adult.csv · 48,842 × 15"}
                  </span>
                </div>
              )}
              {family === "classification" ? (
                <label>
                  Outcome selector
                  <select
                    value={target}
                    onChange={(e) => {
                      setTarget(e.target.value);
                      setAck(false);
                    }}
                  >
                    <option value="">Declare the target</option>
                    <option>annual_income_over_50k</option>
                  </select>
                </label>
              ) : (
                <>
                  <label>
                    Structured field
                    <input value="revenue" readOnly />
                  </label>
                  <label>
                    Context bindings
                    <input value="entity → entity; period → period" readOnly />
                  </label>
                  <label>
                    Native document recipe
                    <select>
                      <option>finance / table_field / Revenue</option>
                    </select>
                  </label>
                  <details>
                    <summary>Recipe details</summary>
                    <p>
                      Metric, Period and Value header aliases. Lines table
                      strategy. Decimal equality, INR, tolerance 0; one_to_many
                      declared association.
                    </p>
                  </details>
                </>
              )}
              <label className="w-check">
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                />{" "}
                Confirm opening existing fixture evidence only.
              </label>
              <button
                className="w-primary"
                disabled={
                  !source || !ack || (family === "classification" && !target)
                }
                onClick={() => setScreen("canvas")}
              >
                Open investigation <ArrowRight size={15} />
              </button>
              <button
                disabled={!source || (family === "classification" && !target)}
                onClick={() => exportConfig(family, target)}
              >
                Export configuration
              </button>
            </section>
            <section>
              <h3>Input preview</h3>
              {!source ? (
                <p>
                  Attach a fixture to inspect its original record structure.
                </p>
              ) : (
                <pre>
                  {family === "connected"
                    ? JSON.stringify(
                        {
                          id: r.id,
                          entity: r.entity,
                          period: r.period,
                          revenue: r.revenue,
                          cutoff: r.cutoff,
                          documents: r.documents.map((d) => d.file),
                        },
                        null,
                        2,
                      )
                    : JSON.stringify(c.preview, null, 2)}
                </pre>
              )}
              <div className="w-explanation">
                <h3>Bind meaning before inspection</h3>
                <p>
                  Production confirmation is bound to source identities, parsing
                  and effective declarations. Changing those invalidates the
                  result. This workbench keeps setup and source preview in the
                  same work area.
                </p>
              </div>
            </section>
          </div>
        </main>
      ) : screen === "method" ? (
        <main className="w-method">
          <h1>Investigation contract</h1>
          <div className="w-method-columns">
            <section>
              {principles.map(([title, text]) => (
                <article key={title}>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </article>
              ))}
            </section>
            <aside>
              <h3>Artifacts / completed evidence</h3>
              <a
                href={fixtureLink(family, "html")}
                target="_blank"
                rel="noreferrer"
              >
                Original HTML report ↗
              </a>
              <a href={fixtureLink(family, "json")} download>
                Fixture {family === "connected" ? "result" : "summary"} JSON ↓
              </a>
              {family === "connected" && (
                <a href={fixtureLink(family, "pdf")} download>
                  Original PDF report ↓
                </a>
              )}
              <button
                onClick={() =>
                  download("prototype-workbench-review.json", {
                    prototype: true,
                    dispositions: reviews,
                    notes,
                  })
                }
              >
                <Download size={14} /> Separate review snapshot
              </button>
              <details>
                <summary>Implemented capabilities</summary>
                {capabilities.map(([id, title, text]) => (
                  <p key={id}>
                    <b>
                      {id} / {title}
                    </b>
                    <br />
                    {text}
                  </p>
                ))}
                <p>M8 audio deferred. Two interactive setup examples.</p>
              </details>
              <button onClick={() => setScreen("canvas")}>
                Return to canvas
              </button>
            </aside>
          </div>
        </main>
      ) : (
        <>
          <div className="w-toolbar">
            <span>
              {family === "connected"
                ? `${r.id} / revenue / ${statusLabel(r.status)}`
                : `${f.code} / ${f.severity}`}
            </span>
            <div>
              <button onClick={() => setSplit(!split)} aria-pressed={split}>
                <Columns2 size={14} />
                {split ? "Side by side" : "Stacked"}
              </button>
              <button
                onClick={() => setShowLedger(!showLedger)}
                aria-pressed={showLedger}
              >
                Coverage ledger
              </button>
              <button
                aria-label="Toggle contextual inspector"
                onClick={() => setInspect(!inspect)}
              >
                {inspect ? (
                  <PanelRightClose size={15} />
                ) : (
                  <PanelRightOpen size={15} />
                )}
              </button>
            </div>
          </div>
          <div className={`w-grid ${inspect ? "" : "w-no-inspector"}`}>
            <aside className="w-explorer">
              <h2>
                {family === "connected"
                  ? "RECORD EXPLORER"
                  : "FINDING EXPLORER"}
              </h2>
              {family === "connected" ? (
                <>
                  <div className="w-search">
                    <Search size={13} />
                    <input
                      aria-label="Search record explorer"
                      value={query}
                      placeholder="Find a record…"
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  <select
                    aria-label="Filter record explorer"
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                  >
                    <option value="all">All 20 records</option>
                    <option value="violated">Discrepancy</option>
                    <option value="conflicting_evidence">Conflict</option>
                    <option value="satisfied">Agreement</option>
                  </select>
                  <div className="w-tree">
                    {filtered.map((x) => (
                      <button
                        key={x.id}
                        className={id === x.id ? "active" : ""}
                        onClick={() => {
                          setId(x.id);
                          setDocumentIndex(0);
                        }}
                      >
                        <span className={`w-dot ${x.status}`} />
                        <span>{x.id}</span>
                        <small>{x.documents.length}</small>
                      </button>
                    ))}
                    {!filtered.length && <p>No matching records.</p>}
                  </div>
                </>
              ) : (
                <div className="w-finding-tree">
                  {findings.map((x, i) => (
                    <button
                      key={x.code}
                      className={findingIndex === i ? "active" : ""}
                      onClick={() => setFindingIndex(i)}
                    >
                      <span>{String(i + 1).padStart(2, "0")}</span>
                      <div>
                        {x.title}
                        <small>{x.severity}</small>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              <div className="w-explorer-foot">
                {family === "connected"
                  ? "20 records / 21 documents"
                  : "48,842 rows / 15 columns"}
                <br />
                Sources frozen in fixture
              </div>
            </aside>
            <main className="w-canvas">
              <div className="w-canvas-meta">
                <span>
                  {family === "connected"
                    ? "DECLARED RECORD ↔ SOURCE EVIDENCE"
                    : "FINDING ↔ RECORDED POPULATION"}
                </span>
                <button
                  onClick={() => setInspect(!inspect)}
                  aria-label="Expand working canvas"
                >
                  <Maximize2 size={13} />
                </button>
              </div>
              <div className="w-size">
                <label>
                  Record pane width{" "}
                  <input
                    type="range"
                    min="30"
                    max="65"
                    value={width}
                    onChange={(e) => setWidth(Number(e.target.value))}
                  />
                  <span>{width}%</span>
                </label>
              </div>
              <div
                className={`w-surfaces ${split ? "" : "stacked"}`}
                style={{
                  gridTemplateColumns: split ? `${width}% 1fr` : undefined,
                }}
              >
                <section className="w-record-pane">
                  <div className="w-source-tab">
                    <Table2 size={12} />
                    {family === "connected"
                      ? "records.csv"
                      : "Adult / finding context"}
                    <span>read only</span>
                  </div>
                  {family === "connected" ? (
                    <>
                      <div className="w-record-heading">
                        <span>STRUCTURED RECORD</span>
                        <h1>{r.id}</h1>
                        <p>
                          Entity {r.entity} / {r.period}
                        </p>
                      </div>
                      <dl className="w-record-fields">
                        <dt>revenue</dt>
                        <dd className="w-selected-field">
                          ₹{money(r.revenue)}
                          <small>INR · decimal</small>
                        </dd>
                        <dt>cutoff</dt>
                        <dd>{r.cutoff}</dd>
                        <dt>claim</dt>
                        <dd>{r.claim}</dd>
                      </dl>
                      <div className="w-binding">
                        <span>ASSOCIATION</span>
                        <p>entity + period</p>
                        <small>supporting_evidence / one_to_many</small>
                      </div>
                    </>
                  ) : (
                    <div className="w-class-finding">
                      <span className="w-source-label">
                        {f.severity.toUpperCase()} / CLASSIFICATION
                      </span>
                      <h1>{f.title}</h1>
                      <p>{f.finding}</p>
                      <blockquote>{f.evidence}</blockquote>
                      <h3>Next step</h3>
                      <p>{f.recommendation}</p>
                      <small>{f.score_effect}</small>
                    </div>
                  )}
                </section>
                <div
                  className="w-divider"
                  style={{ left: `calc(${width}% - 3px)` }}
                  role="separator"
                  aria-label="Adjust record pane width"
                  aria-orientation="vertical"
                  aria-valuenow={width}
                  aria-valuemin={30}
                  aria-valuemax={65}
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "ArrowLeft")
                      setWidth((x) => Math.max(30, x - 2));
                    if (e.key === "ArrowRight")
                      setWidth((x) => Math.min(65, x + 2));
                  }}
                  onPointerDown={(e) => {
                    e.currentTarget.setPointerCapture(e.pointerId);
                  }}
                  onPointerMove={(e) => {
                    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
                      const box =
                        e.currentTarget.parentElement!.getBoundingClientRect();
                      setWidth(
                        Math.min(
                          65,
                          Math.max(
                            30,
                            Math.round(
                              ((e.clientX - box.left) / box.width) * 100,
                            ),
                          ),
                        ),
                      );
                    }
                  }}
                  onPointerUp={(e) =>
                    e.currentTarget.releasePointerCapture(e.pointerId)
                  }
                >
                  <i />
                </div>
                <section className="w-document-pane">
                  <div className="w-source-tab">
                    <FileText size={12} />
                    {family === "connected"
                      ? doc.file
                      : "Stored classification evidence"}
                    <span>
                      {family === "connected"
                        ? "physical page 1"
                        : "validation corpus"}
                    </span>
                  </div>
                  {family === "connected" ? (
                    <>
                      <div className="w-doc-controls">
                        <select
                          aria-label="Choose source document"
                          value={documentIndex}
                          onChange={(e) =>
                            setDocumentIndex(Number(e.target.value))
                          }
                        >
                          {r.documents.map((d, i) => (
                            <option value={i} key={d.file}>
                              {d.file}
                            </option>
                          ))}
                        </select>
                        <button
                          className={format === "excerpt" ? "active" : ""}
                          onClick={() => setFormat("excerpt")}
                        >
                          Excerpt
                        </button>
                        <button
                          className={format === "pdf" ? "active" : ""}
                          onClick={() => setFormat("pdf")}
                        >
                          Original PDF
                        </button>
                      </div>
                      {format === "pdf" ? (
                        <iframe
                          className="w-pdf"
                          title={`Original synthetic ${doc.file}`}
                          src={`/fixtures/${doc.file}#page=1`}
                        />
                      ) : (
                        <div className="w-paper">
                          <span className="w-paper-kicker">
                            SYNTHETIC SOURCE / NATIVE PDF
                          </span>
                          <h2>
                            Company {r.id}
                            <br />
                            financial evidence
                          </h2>
                          <div className="w-paper-rule" />
                          <table>
                            <thead>
                              <tr>
                                <th>Metric</th>
                                <th>Period</th>
                                <th>Value</th>
                              </tr>
                            </thead>
                            <tbody>
                              <tr>
                                <td>Revenue</td>
                                <td>FY2025</td>
                                <td
                                  className={
                                    documentValue(doc.text) !== r.revenue
                                      ? "w-mismatch"
                                      : ""
                                  }
                                >
                                  {money(documentValue(doc.text))}
                                </td>
                              </tr>
                            </tbody>
                          </table>
                          <p>{doc.text.split("Business status: ")[1]}</p>
                          <footer>
                            Reconstructed source excerpt / physical page 1<br />
                            Extraction: native text and lines table strategy
                          </footer>
                          <a
                            href={`/fixtures/${doc.file}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open original PDF in a separate tab ↗
                          </a>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="w-class-source">
                      <h3>Recorded populations</h3>
                      <div className="w-score-path">
                        <b>89.15</b>
                        <ArrowRight size={20} />
                        <b>69</b>
                        <span>evidence mean → guardrail</span>
                      </div>
                      <p>
                        Target balance 47.86 causes the critical-sub-score cap.
                        Conflict evidence does not alter the score.
                      </p>
                      {findingIndex === 0 ? (
                        <>
                          <table>
                            <thead>
                              <tr>
                                <th>CSV row</th>
                                <th>Age</th>
                                <th>Outcome</th>
                              </tr>
                            </thead>
                            <tbody>
                              {c.conflict_example.map((x) => (
                                <tr key={x.row}>
                                  <td>{x.row}</td>
                                  <td>{x.age}</td>
                                  <td>{x.annual_income_over_50k}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          <p>
                            One actual conflict group. All 14 recorded input
                            features agree.
                          </p>
                        </>
                      ) : findingIndex === 1 ? (
                        <table>
                          <thead>
                            <tr>
                              <th>Outcome</th>
                              <th>Rows</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(c.class_counts).map(([name, n]) => (
                              <tr key={name}>
                                <td>{name}</td>
                                <td>{n.toLocaleString()}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      ) : (
                        <p>
                          {f.evidence} This finding requires domain review; no
                          automatic correction is implied.
                        </p>
                      )}
                      <a
                        href="/fixtures/adult-report.html"
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open stored full report ↗
                      </a>
                    </div>
                  )}
                </section>
              </div>
              {showLedger && (
                <section className="w-ledger">
                  <button
                    onClick={() => setShowLedger(false)}
                    aria-label="Collapse coverage ledger"
                  >
                    <ChevronDown size={14} />
                  </button>
                  <strong>COVERAGE LEDGER</strong>
                  {family === "connected" ? (
                    <>
                      <span>
                        <b>20</b> records
                      </span>
                      <span>
                        <b>21</b> occurrences
                      </span>
                      <span>
                        <b>0</b> incomplete
                      </span>
                      <span>
                        Method <b>decimal</b>
                      </span>
                    </>
                  ) : (
                    <>
                      <span>
                        <b>48,842</b> labeled rows
                      </span>
                      <span>
                        <b>5</b> conflict groups
                      </span>
                      <span>
                        <b>10</b> affected rows
                      </span>
                    </>
                  )}
                  <p>
                    {family === "connected"
                      ? "All admitted record comparisons retained. Complete extraction does not establish document layout assurance. Optional NLI scope is distinct."
                      : "Excerpt shown above; full source evidence remains in the existing report. Classification policy only."}
                  </p>
                </section>
              )}
            </main>
            {inspect && (
              <aside className="w-inspector">
                <div className="w-inspector-title">
                  CONTEXTUAL INSPECTOR{" "}
                  <button
                    onClick={() => setInspect(false)}
                    aria-label="Close contextual inspector"
                  >
                    <X size={13} />
                  </button>
                </div>
                <nav>
                  {["rule", "review"].map((x) => (
                    <button
                      className={inspectorTab === x ? "active" : ""}
                      key={x}
                      onClick={() => setInspectorTab(x)}
                    >
                      {x}
                    </button>
                  ))}
                </nav>
                {inspectorTab === "rule" ? (
                  <div className="w-inspector-inner">
                    <span className="w-source-label">
                      {family === "connected"
                        ? statusLabel(r.status)
                        : f.severity}
                    </span>
                    <h2>
                      {family === "connected"
                        ? "Reconciliation"
                        : "Interpretation"}
                    </h2>
                    {family === "connected" ? (
                      <>
                        <dl>
                          <dt>Field</dt>
                          <dd>revenue</dd>
                          <dt>Comparison</dt>
                          <dd>decimal</dd>
                          <dt>Unit / currency</dt>
                          <dd>INR / INR</dd>
                          <dt>Tolerance</dt>
                          <dd>0</dd>
                          <dt>Eligible sources</dt>
                          <dd>{r.documents.length}</dd>
                          <dt>Authority</dt>
                          <dd>not declared</dd>
                        </dl>
                        <div className="w-inspector-callout">
                          <h3>
                            {r.status === "conflicting_evidence"
                              ? "Keep competing evidence visible"
                              : r.status === "violated"
                                ? "Inspect the discrepancy"
                                : "Agreement in declared scope"}
                          </h3>
                          <p>
                            {r.status === "conflicting_evidence"
                              ? "One eligible PDF agrees and another differs. The agreeing document cannot suppress the conflict."
                              : r.status === "violated"
                                ? "The source reports ₹12,00,000 against ₹1,20,00,000 in the record. Check source provenance before choosing a value."
                                : "The record and eligible source share a decimal value under the declared rule. This does not establish truth."}
                          </p>
                        </div>
                      </>
                    ) : (
                      <>
                        <p>{f.modeling_impact}</p>
                        <h3>Score effect</h3>
                        <p>{f.score_effect}</p>
                      </>
                    )}
                    <h3>Evidence access</h3>
                    <p>
                      Copied fixture sources only. Production source resolution
                      verifies exact identities in an authorized local root.
                    </p>
                    <button onClick={() => setScreen("method")}>
                      Methods and limitations →
                    </button>
                  </div>
                ) : (
                  <div className="w-inspector-inner">
                    <h2>Separate review</h2>
                    <label>
                      Disposition
                      <select
                        value={reviews[selected] || "unreviewed"}
                        onChange={(e) =>
                          setReviews({ ...reviews, [selected]: e.target.value })
                        }
                      >
                        {["unreviewed", "confirm", "dismiss", "unresolved"].map(
                          (x) => (
                            <option key={x}>{x}</option>
                          ),
                        )}
                      </select>
                    </label>
                    <label>
                      Reviewer note
                      <textarea
                        placeholder="Record the reasoning…"
                        value={notes[selected] || ""}
                        onChange={(e) =>
                          setNotes({ ...notes, [selected]: e.target.value })
                        }
                      />
                    </label>
                    <p>
                      Simulated memory state. Analytical values remain
                      unchanged.
                    </p>
                    <button
                      onClick={() =>
                        download("prototype-workbench-review.json", {
                          prototype: true,
                          dispositions: reviews,
                          notes,
                        })
                      }
                    >
                      <Download size={13} /> Export review snapshot
                    </button>
                  </div>
                )}
              </aside>
            )}
          </div>
        </>
      )}
      <footer className="w-status">
        <span>◉ Fixture mode / no worker running</span>
        <span>
          {family === "connected"
            ? "Native PDF · physical page locator"
            : "UCI Adult · recorded classification evidence"}
        </span>
        <span>03 / EVIDENCE WORKBENCH</span>
      </footer>
    </div>
  );
}
