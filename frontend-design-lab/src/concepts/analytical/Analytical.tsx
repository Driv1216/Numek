import { useState } from "react";
import {
  ArrowRight,
  Plus,
  SlidersHorizontal,
  Download,
  X,
  Table2,
  ChartColumn,
  Info,
  RefreshCw,
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
import "./analytical.css";
export function Analytical() {
  const [family, setFamily] = useState<Family>("connected"),
    [view, setView] = useState("explore"),
    [setup, setSetup] = useState(
      new URLSearchParams(location.search).get("view") === "new",
    ),
    [status, setStatus] = useState("all"),
    [record, setRecord] = useState("A019"),
    [chartMode, setChartMode] = useState("chart"),
    [outcome, setOutcome] = useState("all"),
    [bin, setBin] = useState<number | null>(null),
    [source, setSource] = useState(false),
    [target, setTarget] = useState(""),
    [ack, setAck] = useState(false),
    [normalize, setNormalize] = useState(false),
    [findingIndex, setFindingIndex] = useState(1),
    [reviews, setReviews] = useState<Record<string, string>>({});
  const r = records.find((x) => x.id === record)!;
  const population = records.filter(
    (x) => status === "all" || x.status === status,
  );
  const selectedBin = bin === null ? null : c.hour_bins[bin];
  const total =
    outcome === "all"
      ? c.row_count
      : c.class_counts[outcome as keyof typeof c.class_counts];
  const selectedCount = selectedBin
    ? Object.entries(selectedBin.counts).reduce(
        (sum, [key, n]) => sum + (outcome === "all" || outcome === key ? n : 0),
        0,
      )
    : total;
  const examples = selectedBin
    ? outcome === "all"
      ? Object.values(selectedBin.examples).flat()
      : selectedBin.examples[outcome as keyof typeof selectedBin.examples]
    : c.preview.filter(
        (x) => outcome === "all" || x.annual_income_over_50k === outcome,
      );
  const f = findings[findingIndex];
  const max = Math.max(
    ...c.hour_bins.map((b) =>
      Object.entries(b.counts).reduce(
        (sum, [key, n]) => sum + (outcome === "all" || outcome === key ? n : 0),
        0,
      ),
    ),
  );
  const changeFamily = (value: Family) => {
    setFamily(value);
    setSource(false);
    setTarget("");
    setAck(false);
    setView("explore");
    setStatus("all");
    setBin(null);
    setChartMode("chart");
  };
  const resetFilters = () => {
    setStatus("all");
    setOutcome("all");
    setBin(null);
  };
  return (
    <div className="analytical">
      <header className="a-header">
        <a href="/analytical">
          <span className="a-mark">∷</span>
          <b>
            NUMEK<span>DataTrust / Analytical Studio</span>
          </b>
        </a>
        <div className="a-header-right">
          <span>Local fixture · no execution</span>
          <button
            onClick={() => {
              setSetup(true);
              setSource(false);
              setTarget("");
              setAck(false);
            }}
          >
            <Plus size={15} /> New analysis
          </button>
        </div>
      </header>
      <div className="a-navigation">
        <label>
          Investigation
          <select
            value={family}
            onChange={(e) => changeFamily(e.target.value as Family)}
          >
            <option value="connected">Financial evidence / M9</option>
            <option value="classification">Adult classification</option>
          </select>
        </label>
        <nav>
          {[
            ["explore", "Explore populations"],
            ["findings", "Finding interpretation"],
            ["method", "Methods & exports"],
          ].map(([key, name]) => (
            <button
              className={view === key ? "active" : ""}
              key={key}
              onClick={() => setView(key)}
            >
              {name}
            </button>
          ))}
        </nav>
      </div>
      {setup ? (
        <main className="a-setup">
          <div className="a-setup-heading">
            <SlidersHorizontal size={22} />
            <h1>Set up an analytical view.</h1>
            <button
              onClick={() => setSetup(false)}
              aria-label="Close analytical setup"
            >
              <X size={18} />
            </button>
          </div>
          <p>
            Inspect a known source and make its meaning explicit. This parameter
            tray opens stored fixture results.
          </p>
          <div className="a-parameters">
            <label>
              01 / Analysis type
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
            <div>
              <span className="a-parameter-label">02 / Input population</span>
              <button
                className="a-source-button"
                onClick={() => setSource(true)}
              >
                {family === "connected"
                  ? "Select 20-record synthetic collection"
                  : "Select public Adult fixture"}
                <span>{source ? "Selected" : "→"}</span>
              </button>
            </div>
            <label>
              03 / Declaration
              {family === "classification" ? (
                <select
                  value={target}
                  onChange={(e) => {
                    setTarget(e.target.value);
                    setAck(false);
                  }}
                >
                  <option value="">Declare an outcome</option>
                  <option>annual_income_over_50k</option>
                </select>
              ) : (
                <select>
                  <option>revenue / decimal / INR / tolerance 0</option>
                </select>
              )}
            </label>
          </div>
          {source && (
            <section className="a-input-preview">
              <h3>Input inspection</h3>
              <div className="a-table">
                <table>
                  <thead>
                    <tr>
                      {(family === "classification"
                        ? ["Age", "Education", "Hours/week", "Outcome"]
                        : ["Record", "Entity", "Period", "Revenue / INR"]
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
                          .map((x) => ({
                            id: x.id,
                            entity: x.entity,
                            period: x.period,
                            revenue: x.revenue,
                          }))
                    ).map((row, i) => (
                      <tr key={i}>
                        {Object.values(row).map((x, j) => (
                          <td key={j}>{x}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p>
                {family === "connected"
                  ? "Association: entity + period, one_to_many. Recipe: finance table / Revenue row / lines strategy. 20 source records and 21 native PDFs."
                  : "48,842 rows / 15 columns. Preview shows 5 rows. Remaining columns become input features after explicit target selection."}
              </p>
            </section>
          )}
          <label className="a-check">
            <input
              type="checkbox"
              checked={ack}
              onChange={(e) => setAck(e.target.checked)}
            />{" "}
            I understand that this opens stored fixture measurements. No real
            analytical execution.
          </label>
          <div className="a-actions">
            <button
              className="a-primary"
              disabled={
                !source || !ack || (family === "classification" && !target)
              }
              onClick={() => {
                setSetup(false);
                setView("explore");
                resetFilters();
              }}
            >
              Open analytical fixture <ArrowRight size={16} />
            </button>
            <button
              disabled={!source || (family === "classification" && !target)}
              onClick={() => exportConfig(family, target)}
            >
              Export parameter preview
            </button>
          </div>
        </main>
      ) : view === "method" ? (
        <main className="a-method">
          <span className="a-eyebrow">
            SOURCE TRANSPARENCY / INTERPRETATION
          </span>
          <h1>Know what the marks mean.</h1>
          <div className="a-method-grid">
            <div>
              {principles.map(([title, text]) => (
                <section key={title}>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </section>
              ))}
            </div>
            <aside>
              <h3>Source artifacts</h3>
              <a
                href={fixtureLink(family, "html")}
                target="_blank"
                rel="noreferrer"
              >
                Existing HTML report ↗
              </a>
              <a href={fixtureLink(family, "json")} download>
                Fixture {family === "connected" ? "result" : "summary"} JSON ↓
              </a>
              {family === "connected" && (
                <a href={fixtureLink(family, "pdf")} download>
                  Existing PDF ↓
                </a>
              )}
              <button
                onClick={() =>
                  download("prototype-analytical-review.json", {
                    prototype: true,
                    entries: reviews,
                  })
                }
              >
                Separate prototype review JSON ↓
              </button>
              <p>
                Adult hours bins are descriptive counts computed from the pinned
                public CSV. They are not a new diagnostic or score. M9 values
                come directly from the synthetic native PDFs.
              </p>
              <details>
                <summary>Implemented capability map</summary>
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
                  M8 audio deferred. Classification and M9 setup are simulated
                  here.
                </p>
              </details>
            </aside>
          </div>
        </main>
      ) : view === "findings" ? (
        <main className="a-finding-view">
          <span className="a-eyebrow">EVIDENCE → INTERPRETATION → ACTION</span>
          <h1>
            {family === "connected"
              ? "Two different disagreements."
              : "Four reasons to look closer."}
          </h1>
          <div className="a-finding-columns">
            <nav>
              {family === "classification"
                ? findings.map((x, i) => (
                    <button
                      className={findingIndex === i ? "active" : ""}
                      key={x.code}
                      onClick={() => setFindingIndex(i)}
                    >
                      <span>{String(i + 1).padStart(2, "0")}</span>
                      {x.title}
                      <small>{x.severity}</small>
                    </button>
                  ))
                : records
                    .filter((x) => x.status !== "satisfied")
                    .map((x) => (
                      <button
                        className={record === x.id ? "active" : ""}
                        key={x.id}
                        onClick={() => setRecord(x.id)}
                      >
                        <span>{x.id}</span>
                        {statusLabel(x.status)}
                        <small>{x.documents.length} sources</small>
                      </button>
                    ))}
            </nav>
            <article>
              {family === "classification" ? (
                <>
                  <h2>{f.title}</h2>
                  <p>{f.finding}</p>
                  <blockquote>{f.evidence}</blockquote>
                  <h3>Modeling implication</h3>
                  <p>{f.modeling_impact}</p>
                  <h3>Recommended next step</h3>
                  <p>{f.recommendation}</p>
                  <p className="a-source-note">{f.score_effect}</p>
                  {findingIndex === 0 && (
                    <>
                      <h3>One actual conflicting-label group</h3>
                      <div className="a-table">
                        <table>
                          <thead>
                            <tr>
                              <th>CSV row</th>
                              <th>Age</th>
                              <th>Hours/week</th>
                              <th>Outcome</th>
                            </tr>
                          </thead>
                          <tbody>
                            {c.conflict_example.map((x) => (
                              <tr key={x.row}>
                                <td>{x.row}</td>
                                <td>{x.age}</td>
                                <td>{x.hours_per_week}</td>
                                <td>{x.annual_income_over_50k}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <p className="a-source-note">
                        All 14 recorded features agree. Row numbers include the
                        header.
                      </p>
                    </>
                  )}
                  <button
                    className="a-primary"
                    onClick={() => {
                      setView("explore");
                      setOutcome("all");
                      setBin(null);
                    }}
                  >
                    Inspect recorded population <ArrowRight size={15} />
                  </button>
                  <a
                    href="/fixtures/adult-report.html"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Open full stored evidence ↗
                  </a>
                </>
              ) : (
                <>
                  <h2>
                    {r.id} / {statusLabel(r.status)}
                  </h2>
                  <p>
                    {r.status === "conflicting_evidence"
                      ? "Two eligible sources contain competing decimal values. The agreeing source cannot hide the conflict."
                      : "The structured record and eligible document differ. Inspect literal evidence before deciding which value to retain."}
                  </p>
                  <div className="a-value-compare">
                    <div>
                      <span>STRUCTURED RECORD</span>
                      <b>₹{money(r.revenue)}</b>
                    </div>
                    {r.documents.map((d) => (
                      <div key={d.file}>
                        <span>{d.file}</span>
                        <b>₹{money(documentValue(d.text))}</b>
                        <a
                          href={`/fixtures/${d.file}`}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Original synthetic PDF ↗
                        </a>
                      </div>
                    ))}
                  </div>
                  <h3>What this comparison means</h3>
                  <p>
                    Revenue / INR / exact decimal equality / FY2025. Context is
                    supplied; authority is undeclared. No M9 overall score or
                    source-truth claim.
                  </p>
                  <label>
                    Separate reviewer disposition
                    <select
                      value={reviews[r.id] || "unreviewed"}
                      onChange={(e) =>
                        setReviews({ ...reviews, [r.id]: e.target.value })
                      }
                    >
                      {["unreviewed", "confirm", "dismiss", "unresolved"].map(
                        (x) => (
                          <option key={x}>{x}</option>
                        ),
                      )}
                    </select>
                  </label>
                  <button
                    onClick={() => {
                      setView("explore");
                      setStatus("all");
                    }}
                  >
                    Locate in full population →
                  </button>
                </>
              )}
            </article>
          </div>
        </main>
      ) : (
        <main className="a-explore">
          <div className="a-title-row">
            <div>
              <span className="a-eyebrow">
                {family === "connected"
                  ? "RECONCILIATION / 20 RECORDS / 21 DOCUMENTS"
                  : "CLASSIFICATION / 48,842 LABELED ROWS"}
              </span>
              <h1>
                {family === "connected"
                  ? "Agreement is a starting point."
                  : "See the population behind the finding."}
              </h1>
              <p>
                {family === "connected"
                  ? "Compare each recorded value with the eligible documentary evidence. Select a mark to trace its source."
                  : "Explore the observed hours-per-week distribution across outcome classes. Select a bin to inspect its population."}
              </p>
            </div>
            <button aria-label="Clear linked filters" onClick={resetFilters}>
              <RefreshCw size={14} /> Reset view
            </button>
          </div>
          <div className="a-filter-row">
            {family === "connected" ? (
              <div className="a-status-filters">
                {[
                  ["all", "All records", 20],
                  ["satisfied", "Agreement", 18],
                  ["violated", "Discrepancy", 1],
                  ["conflicting_evidence", "Conflict", 1],
                ].map(([key, label, n]) => (
                  <button
                    className={status === key ? "active" : ""}
                    key={key}
                    onClick={() => {
                      setStatus(String(key));
                      const next = records.find(
                        (x) => key === "all" || x.status === key,
                      );
                      if (next) setRecord(next.id);
                    }}
                  >
                    <span className={`a-status-dot ${key}`} />
                    {label}
                    <b>{n}</b>
                  </button>
                ))}
              </div>
            ) : (
              <label>
                Outcome population
                <select
                  value={outcome}
                  onChange={(e) => {
                    setOutcome(e.target.value);
                    setBin(null);
                  }}
                >
                  <option value="all">All labeled rows / 48,842</option>
                  <option value="<=50K">≤50K / 37,155</option>
                  <option value=">50K">&gt;50K / 11,687</option>
                </select>
              </label>
            )}
            <div className="a-chart-switch">
              <button
                aria-label="Show chart"
                className={chartMode === "chart" ? "active" : ""}
                onClick={() => setChartMode("chart")}
              >
                <ChartColumn size={15} />
              </button>
              <button
                aria-label="Show chart data table"
                className={chartMode === "table" ? "active" : ""}
                onClick={() => setChartMode("table")}
              >
                <Table2 size={15} />
              </button>
            </div>
          </div>
          <section className="a-chart-area">
            <div className="a-chart-caption">
              <h2>
                {family === "connected"
                  ? "Recorded revenue vs. documentary revenue"
                  : "Observed hours per week"}
              </h2>
              <div className="a-legend">
                {family === "connected" ? (
                  <>
                    <span>
                      <i className="record" /> Structured record
                    </span>
                    <span>
                      <i className="document" /> Native PDF
                    </span>
                  </>
                ) : (
                  <>
                    <span>
                      <i className="record" /> ≤50K
                    </span>
                    <span>
                      <i className="document" /> &gt;50K
                    </span>
                    <label>
                      <input
                        type="checkbox"
                        checked={normalize}
                        onChange={(e) => setNormalize(e.target.checked)}
                      />{" "}
                      Show % of selected population
                    </label>
                  </>
                )}
              </div>
            </div>
            {chartMode === "table" ? (
              <div className="a-table">
                <table>
                  <thead>
                    <tr>
                      {(family === "connected"
                        ? [
                            "Record",
                            "Structured / INR",
                            "Documents / INR",
                            "Result",
                          ]
                        : [
                            "Hours / week",
                            "≤50K rows",
                            ">50K rows",
                            "Selected rows",
                          ]
                      ).map((x) => (
                        <th key={x}>{x}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {family === "connected"
                      ? population.map((x) => (
                          <tr key={x.id}>
                            <td>
                              <button onClick={() => setRecord(x.id)}>
                                {x.id}
                              </button>
                            </td>
                            <td>{money(x.revenue)}</td>
                            <td>
                              {x.documents
                                .map((d) => money(documentValue(d.text)))
                                .join(" / ")}
                            </td>
                            <td>{statusLabel(x.status)}</td>
                          </tr>
                        ))
                      : c.hour_bins.map((b, i) => (
                          <tr key={b.label}>
                            <td>
                              <button onClick={() => setBin(i)}>
                                {b.label}
                              </button>
                            </td>
                            <td>
                              {outcome === "all" || outcome === "<=50K"
                                ? b.counts["<=50K"].toLocaleString()
                                : "— excluded"}
                            </td>
                            <td>
                              {outcome === "all" || outcome === ">50K"
                                ? b.counts[">50K"].toLocaleString()
                                : "— excluded"}
                            </td>
                            <td>
                              {(
                                (outcome === "all" || outcome === "<=50K"
                                  ? b.counts["<=50K"]
                                  : 0) +
                                (outcome === "all" || outcome === ">50K"
                                  ? b.counts[">50K"]
                                  : 0)
                              ).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                  </tbody>
                </table>
              </div>
            ) : family === "connected" ? (
              <div className="a-plot-wrap">
                <svg
                  viewBox="0 0 1000 325"
                  role="group"
                  aria-label="Revenue by record and eligible native PDF, in INR millions"
                >
                  <text x="12" y="17" className="a-axis-title">
                    INR / MILLIONS
                  </text>
                  {[0, 3, 6, 9, 12].map((value) => (
                    <g key={value}>
                      <line
                        x1="60"
                        x2="960"
                        y1={270 - (value / 12) * 220}
                        y2={270 - (value / 12) * 220}
                        className="a-grid-line"
                      />
                      <text
                        x="42"
                        y={274 - (value / 12) * 220}
                        textAnchor="end"
                        className="a-axis"
                      >
                        {value}
                      </text>
                    </g>
                  ))}
                  {population.map((x, i) => {
                    const px =
                      population.length === 1
                        ? 500
                        : 80 + i * (860 / (population.length - 1));
                    return (
                      <g
                        key={x.id}
                        role="button"
                        tabIndex={0}
                        aria-label={`${x.id}, ${statusLabel(x.status)}, structured 12 million INR`}
                        onClick={() => setRecord(x.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setRecord(x.id);
                          }
                        }}
                        className="a-chart-mark"
                      >
                        {record === x.id && (
                          <rect
                            x={px - 17}
                            y="35"
                            width="34"
                            height="247"
                            fill="#e8eee6"
                          />
                        )}
                        <line
                          x1={px}
                          x2={px}
                          y1="50"
                          y2={Math.max(
                            ...x.documents.map(
                              (d) =>
                                270 -
                                (Number(documentValue(d.text)) / 12000000) *
                                  220,
                            ),
                          )}
                          stroke={
                            x.status === "satisfied" ? "#8daca8" : "#b38653"
                          }
                          strokeWidth="2"
                          strokeDasharray="3 4"
                        />
                        <path
                          d={`M ${px} 43 l 7 7 l -7 7 l -7 -7 Z`}
                          fill="#447b89"
                        />
                        {x.documents.map((d, j) => (
                          <circle
                            key={d.file}
                            cx={
                              px +
                              (x.documents.length > 1 ? (j === 0 ? -3 : 3) : 0)
                            }
                            cy={
                              270 -
                              (Number(documentValue(d.text)) / 12000000) * 220
                            }
                            r={record === x.id ? 7 : 5}
                            fill="#f7faf8"
                            stroke={
                              x.status === "satisfied" ? "#719b88" : "#b17a41"
                            }
                            strokeWidth="2.5"
                          />
                        ))}
                        <text
                          x={px}
                          y="303"
                          textAnchor="middle"
                          className="a-axis"
                        >
                          {x.id}
                        </text>
                      </g>
                    );
                  })}
                  <text x="60" y="324" className="a-axis-title">
                    EXPLICIT RECORD ID / CATEGORICAL AXIS · NO TEMPORAL ORDER
                  </text>
                </svg>
              </div>
            ) : (
              <div className="a-histogram">
                <div className="a-histogram-axis">
                  <span>
                    {normalize ? "% of selected rows" : "Selected row count"}
                  </span>
                  <span>
                    {normalize
                      ? ((max / total) * 100).toFixed(1) + "%"
                      : max.toLocaleString()}{" "}
                    max bin
                  </span>
                </div>
                <div className="a-bars">
                  {c.hour_bins.map((b, i) => {
                    const first =
                      outcome === "all" || outcome === "<=50K"
                        ? b.counts["<=50K"]
                        : 0;
                    const second =
                      outcome === "all" || outcome === ">50K"
                        ? b.counts[">50K"]
                        : 0;
                    return (
                      <button
                        className={`a-bar-column ${bin === i ? "selected" : ""}`}
                        key={b.label}
                        aria-label={`Hours ${b.label}, ${first + second} selected rows`}
                        onClick={() => setBin(bin === i ? null : i)}
                      >
                        <div
                          className="a-bar-stack"
                          style={{
                            height: `${((first + second) / max) * 100}%`,
                          }}
                        >
                          <i
                            className="a-higher"
                            style={{ flexGrow: second }}
                          />
                          <i className="a-lower" style={{ flexGrow: first }} />
                        </div>
                        <span>{b.label}</span>
                        <small>
                          {normalize
                            ? (((first + second) / total) * 100).toFixed(1) +
                              "%"
                            : (first + second).toLocaleString()}
                        </small>
                      </button>
                    );
                  })}
                </div>
                <div className="a-histogram-axis">
                  <span>HOURS / WEEK · FIXED TEN-HOUR BINS</span>
                  <span>Not an outlier threshold</span>
                </div>
              </div>
            )}
            <div className="a-chart-source">
              <Info size={13} />
              <p>
                {family === "connected"
                  ? `${population.length} of 20 records shown. All structured revenues are INR 12,000,000; source values are INR 12,000,000 or 1,200,000. No uncertainty intervals or statistical relationship are inferred.`
                  : `${total.toLocaleString()} labeled rows in the selected class population. Bin counts computed from the pinned Adult CSV; no new analytical diagnostic is implied.`}
              </p>
              <button
                onClick={() =>
                  download("prototype-chart-data.json", {
                    prototype: true,
                    family,
                    selectedScope: { status, outcome, bin },
                    population:
                      family === "connected"
                        ? population.map((x) => ({
                            id: x.id,
                            revenue: x.revenue,
                            status: x.status,
                            documents: x.documents.map((d) => ({
                              file: d.file,
                              revenue: documentValue(d.text),
                            })),
                          }))
                        : c.hour_bins,
                  })
                }
              >
                <Download size={12} /> Chart data
              </button>
            </div>
          </section>
          {family === "connected" ? (
            <section className="a-linked-evidence">
              <div className="a-selection-summary">
                <span className="a-eyebrow">
                  SELECTED RECORD / {statusLabel(r.status).toUpperCase()}
                </span>
                <h2>
                  {r.id}
                  <small>{r.period} · revenue</small>
                </h2>
                <p>₹{money(r.revenue)} in the structured record</p>
                <button onClick={() => setView("findings")}>
                  Read interpretation <ArrowRight size={14} />
                </button>
              </div>
              <div className="a-document-evidence">
                {r.documents.map((d) => (
                  <article key={d.file}>
                    <span>NATIVE PDF / PHYSICAL PAGE 1</span>
                    <h3>{d.file}</h3>
                    <b>₹{money(documentValue(d.text))}</b>
                    <p>{d.text.split("Business status: ")[1]}</p>
                    <a
                      href={`/fixtures/${d.file}`}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Inspect original fixture source ↗
                    </a>
                  </article>
                ))}
              </div>
              <aside className="a-coverage">
                <span>COVERAGE / DECIMAL RULE</span>
                <p>
                  <b>20</b> records
                  <br />
                  <b>21</b> candidate occurrences
                  <br />
                  <b>0</b> incomplete records
                </p>
                <small>
                  Complete native extraction does not establish layout
                  assurance. No M9 score.
                </small>
                <button onClick={() => setView("method")}>
                  Scope & methods →
                </button>
              </aside>
            </section>
          ) : (
            <section className="a-linked-class">
              <div>
                <span className="a-eyebrow">LINKED POPULATION</span>
                <h2>
                  {selectedCount.toLocaleString()}{" "}
                  <small>
                    rows{" "}
                    {selectedBin
                      ? `in ${selectedBin.label} hours/week`
                      : "in selected class scope"}
                  </small>
                </h2>
                <p>
                  Examples below are a bounded excerpt of the selected
                  population, with{" "}
                  {outcome === "all"
                    ? "no outcome restriction"
                    : `outcome ${outcome}`}
                  .
                </p>
                <div className="a-table">
                  <table>
                    <thead>
                      <tr>
                        <th>Age</th>
                        <th>Education</th>
                        <th>Hours/week</th>
                        <th>Outcome</th>
                      </tr>
                    </thead>
                    <tbody>
                      {examples.map((x, i) => (
                        <tr key={i}>
                          <td>{x.age}</td>
                          <td>{x.education}</td>
                          <td>{x.hours_per_week}</td>
                          <td>{x.annual_income_over_50k}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {!examples.length && (
                  <p>No examples retained in this selected excerpt.</p>
                )}
              </div>
              <aside>
                <span className="a-eyebrow">CLASSIFICATION SCORE PATH</span>
                <div className="a-score">
                  <b>89.15</b>
                  <ArrowRight size={19} />
                  <b>69</b>
                </div>
                <p>
                  Evidence mean → guarded final score. Target balance 47.86 caps
                  the result; descriptive bin selection does not recompute
                  scoring.
                </p>
                <button onClick={() => setView("findings")}>
                  Interpret the findings →
                </button>
                <a
                  href="/fixtures/adult-report.html"
                  target="_blank"
                  rel="noreferrer"
                >
                  Full stored evidence ↗
                </a>
              </aside>
            </section>
          )}
        </main>
      )}
      <footer className="a-footer">
        <span>NUMEK / ANALYTICAL STUDIO</span>
        <span>Measured populations. Traceable sources.</span>
        <span>05 / FIXTURE PROTOTYPE</span>
      </footer>
    </div>
  );
}
