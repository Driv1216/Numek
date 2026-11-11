import { useState } from "react";
import {
  ArrowUpRight,
  ArrowRight,
  Plus,
  X,
  ChevronDown,
  FileText,
  Download,
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
import "./edition.css";
export function Edition() {
  const [family, setFamily] = useState<Family>("classification"),
    [chapter, setChapter] = useState("conclusions"),
    [intake, setIntake] = useState(
      new URLSearchParams(location.search).get("view") === "new",
    ),
    [target, setTarget] = useState(""),
    [source, setSource] = useState(false),
    [ack, setAck] = useState(false),
    [expanded, setExpanded] = useState<string | null>(null),
    [record, setRecord] = useState("A019"),
    [filter, setFilter] = useState("all"),
    [query, setQuery] = useState(""),
    [review, setReview] = useState<Record<string, string>>({}),
    [purpose, setPurpose] = useState("");
  const r = records.find((x) => x.id === record)!;
  const results = records.filter(
    (x) =>
      (filter === "all" || x.status === filter) &&
      x.id.toLowerCase().includes(query.toLowerCase()),
  );
  const openNew = () => {
    setIntake(true);
    setSource(false);
    setAck(false);
    setTarget("");
  };
  const changeFamily = (f: Family) => {
    setFamily(f);
    setChapter("conclusions");
    setExpanded(null);
    setSource(false);
    setTarget("");
    setAck(false);
  };
  return (
    <div className="edition">
      <header className="e-masthead">
        <a href="/edition">
          NUMEK<span>DataTrust / Decision Edition</span>
        </a>
        <span className="e-issue">
          RELIABILITY REVIEW
          <br />
          LOCAL FIXTURE / EDITION 04
        </span>
        <button onClick={openNew}>
          <Plus size={14} /> New analysis
        </button>
      </header>
      <div className="e-meta">
        <label>
          Investigation{" "}
          <select
            value={family}
            onChange={(e) => changeFamily(e.target.value as Family)}
          >
            <option value="classification">Adult / Classification</option>
            <option value="connected">
              Financial records / Connected evidence
            </option>
          </select>
        </label>
        <span>PUBLIC & SYNTHETIC EXAMPLES · NO ANALYSIS EXECUTED</span>
      </div>
      {intake ? (
        <main className="e-intake">
          <div className="e-intake-head">
            <span>INTAKE / A NEW INVESTIGATION</span>
            <button
              onClick={() => setIntake(false)}
              aria-label="Close intake sheet"
            >
              <X size={18} />
            </button>
          </div>
          <h1>Begin with a question.</h1>
          <p>
            Declare what the data means, then read the stored fixture
            investigation. This sheet simulates setup only.
          </p>
          <div className="e-intake-columns">
            <section>
              <h2>01. The material</h2>
              <label>
                Analysis type
                <select
                  value={family}
                  onChange={(e) => {
                    setFamily(e.target.value as Family);
                    setSource(false);
                    setAck(false);
                  }}
                >
                  <option value="classification">Classification</option>
                  <option value="connected">M9 / Connected evidence</option>
                </select>
              </label>
              <button className="e-source" onClick={() => setSource(true)}>
                <FileText size={20} />
                <span>
                  {family === "classification"
                    ? "Use the public Adult example"
                    : "Use the synthetic financial collection"}
                  <small>
                    {source ? "Fixture selected" : "Inspect source →"}
                  </small>
                </span>
              </button>
              {source && (
                <>
                  <p>
                    {family === "classification"
                      ? "48,842 rows and 15 columns; 5 displayed preview rows."
                      : "20 records and 21 native PDFs. Exact original fixture PDFs remain available."}
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
                </>
              )}
            </section>
            <section>
              <h2>02. The meaning</h2>
              {family === "classification" ? (
                <label>
                  Explicit outcome
                  <select
                    value={target}
                    onChange={(e) => {
                      setTarget(e.target.value);
                      setAck(false);
                    }}
                  >
                    <option value="">Choose the outcome column</option>
                    <option>annual_income_over_50k</option>
                  </select>
                </label>
              ) : (
                <>
                  <p>
                    Revenue is reconciled by exact decimal comparison in INR.
                    Entity and period supply context; the relationship permits
                    multiple documents.
                  </p>
                  <details>
                    <summary>Read the recipe declaration</summary>
                    <pre>
                      {JSON.stringify(
                        {
                          method: "decimal",
                          field: "revenue",
                          unit: "INR",
                          tolerance: "0",
                          cardinality: "one_to_many",
                          layout: "finance",
                          recipe: "table_field",
                          headers: ["Metric", "Period", "Value"],
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </>
              )}
              <label>
                Question or purpose
                <textarea
                  value={purpose}
                  onChange={(e) => {
                    setPurpose(e.target.value);
                    setAck(false);
                  }}
                  placeholder="What decision does this review support?"
                />
              </label>
              <h2>03. The boundary</h2>
              <label className="e-check">
                <input
                  type="checkbox"
                  checked={ack}
                  onChange={(e) => setAck(e.target.checked)}
                />{" "}
                I understand that this opens existing evidence without running
                an analysis.
              </label>
              <div className="e-intake-actions">
                <button
                  className="e-primary"
                  disabled={
                    !source || !ack || (family === "classification" && !target)
                  }
                  onClick={() => {
                    setIntake(false);
                    setChapter("conclusions");
                  }}
                >
                  Read fixture investigation <ArrowRight size={15} />
                </button>
                <button
                  disabled={!source || (family === "classification" && !target)}
                  onClick={() => exportConfig(family, target, { purpose })}
                >
                  Export intake JSON
                </button>
              </div>
            </section>
          </div>
        </main>
      ) : (
        <>
          <nav className="e-contents" aria-label="Report chapters">
            {[
              ["conclusions", "01", "The conclusion"],
              ["evidence", "02", "The evidence"],
              ["method", "03", "Methods & limits"],
              ["export", "04", "The artifacts"],
            ].map(([key, n, label]) => (
              <button
                className={chapter === key ? "active" : ""}
                key={key}
                onClick={() => {
                  setChapter(key);
                  setExpanded(null);
                }}
              >
                <span>{n}</span>
                {label}
              </button>
            ))}
          </nav>
          <main className="e-page">
            <div className="e-running">
              <span>
                {family === "classification"
                  ? "ADULT / CLASSIFICATION"
                  : "FINANCIAL EVIDENCE / M9"}
              </span>
              <span>
                {chapter.toUpperCase()} /{" "}
                {chapter === "conclusions"
                  ? "01"
                  : chapter === "evidence"
                    ? "02"
                    : chapter === "method"
                      ? "03"
                      : "04"}
              </span>
            </div>
            {chapter === "conclusions" ? (
              <>
                <div className="e-title-block">
                  <span className="e-kicker">A COMPLETED INVESTIGATION</span>
                  <h1>
                    {family === "classification" ? (
                      <>
                        The labels deserve
                        <br />a closer look.
                      </>
                    ) : (
                      <>
                        Two records,
                        <br />
                        two different problems.
                      </>
                    )}
                  </h1>
                  <p className="e-deck">
                    {family === "classification"
                      ? "A reliable decision starts with the gaps in the evidence. Adult’s classification review surfaces label disagreement, an uneven outcome population and one numerical field to inspect."
                      : "Most declared revenue comparisons agree. One record differs from its document; another has competing eligible sources. The distinction determines the next review action."}
                  </p>
                </div>
                <div className="e-story-grid">
                  <aside className="e-margin">
                    <span>AT A GLANCE</span>
                    {family === "classification" ? (
                      <>
                        <b>48,842</b>
                        <small>rows / 15 columns</small>
                        <b>
                          69<span>/100</span>
                        </b>
                        <small>Elevated / classification policy</small>
                        <p>
                          Evidence mean 89.15; capped by target-balance
                          guardrail. This is not a model-performance estimate.
                        </p>
                      </>
                    ) : (
                      <>
                        <b>
                          18<span>/20</span>
                        </b>
                        <small>record comparisons agree</small>
                        <b>21</b>
                        <small>source PDFs</small>
                        <p>
                          No overall M9 score. Agreement does not establish
                          source truth.
                        </p>
                      </>
                    )}
                  </aside>
                  <article className="e-reading">
                    <h2>
                      {family === "classification"
                        ? "A qualified starting point."
                        : "Read disagreement precisely."}
                    </h2>
                    <p>
                      {family === "classification"
                        ? "The target’s majority class accounts for 76.07% of labeled rows. A model that predicts only that class can appear accurate while failing the minority outcome. Evaluate each class rather than relying on headline accuracy."
                        : "The discrepancy for A019 compares ₹1,20,00,000 in the structured record with ₹12,00,000 in its eligible source. A020 is different: one document agrees with the record, while a second document reports the lower value. Agreement must not hide competing evidence."}
                    </p>
                    <button
                      className="e-footnote"
                      onClick={() => {
                        setChapter("evidence");
                        setExpanded(
                          family === "classification"
                            ? "target_imbalance"
                            : "A019",
                        );
                      }}
                    >
                      {family === "classification"
                        ? "[1] Inspect the target population"
                        : "[1] Read the original record and documents"}{" "}
                      <ArrowUpRight size={13} />
                    </button>
                    <p>
                      {family === "classification"
                        ? "Five groups share identical recorded inputs and contain opposing labels. The ten rows deserve review, but the evidence alone cannot distinguish labeling error from an omitted time, entity or contextual feature."
                        : "Both findings require source and provenance review. Decimal equality is evaluated under a declared unit, context and tolerance; it cannot determine which source ought to be authoritative."}
                    </p>
                    <button
                      className="e-footnote"
                      onClick={() => {
                        setChapter("evidence");
                        setExpanded(
                          family === "classification"
                            ? "conflicting_target_labels"
                            : "A020",
                        );
                        setRecord("A020");
                      }}
                    >
                      {family === "classification"
                        ? "[2] Examine a conflicting-label group"
                        : "[2] Compare the competing documents"}{" "}
                      <ArrowUpRight size={13} />
                    </button>
                    <div className="e-decision">
                      <span>RECOMMENDED NEXT STEP</span>
                      <h3>
                        {family === "classification"
                          ? "Review context before correcting labels."
                          : "Resolve source authority before changing records."}
                      </h3>
                      <p>
                        {family === "classification"
                          ? "Inspect disagreement, choose class-sensitive evaluation metrics, and verify whether extreme hours-per-week values reflect real cases."
                          : "Inspect original documents and the declared recipe. Record a separate reviewer disposition; keep the original analytical result intact."}
                      </p>
                      <button onClick={() => setChapter("evidence")}>
                        Continue into the evidence <ArrowRight size={16} />
                      </button>
                    </div>
                  </article>
                </div>
              </>
            ) : chapter === "evidence" ? (
              <>
                <h1 className="e-chapter-title">
                  The evidence,
                  <br />
                  in context.
                </h1>
                <p className="e-chapter-intro">
                  {family === "classification"
                    ? "A finding is a claim about the recorded population. Open its detail to see what supports it."
                    : "The whole population stays visible. Move from the declared comparison to its original synthetic source."}
                </p>
                {family === "classification" ? (
                  <div className="e-finding-articles">
                    {findings.map((f, i) => (
                      <article key={f.code}>
                        <button
                          aria-expanded={expanded === f.code}
                          onClick={() =>
                            setExpanded(expanded === f.code ? null : f.code)
                          }
                        >
                          <span>{String(i + 1).padStart(2, "0")}</span>
                          <div>
                            <h2>{f.title}</h2>
                            <p>{f.evidence}</p>
                          </div>
                          <ChevronDown size={20} />
                        </button>
                        {expanded === f.code && (
                          <div className="e-finding-body">
                            <p>{f.finding}</p>
                            <p>{f.modeling_impact}</p>
                            {f.code === "conflicting_target_labels" && (
                              <>
                                <div className="e-table">
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
                                </div>
                                <p className="e-source-note">
                                  One actual group, all 14 input features
                                  identical. Original CSV line references
                                  include the header.
                                </p>
                              </>
                            )}
                            {f.code === "target_imbalance" && (
                              <div className="e-table">
                                <table>
                                  <thead>
                                    <tr>
                                      <th>Target value</th>
                                      <th>Labeled rows</th>
                                      <th>Population</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {Object.entries(c.class_counts).map(
                                      ([name, n]) => (
                                        <tr key={name}>
                                          <td>{name}</td>
                                          <td>{n.toLocaleString()}</td>
                                          <td>
                                            {((n / c.row_count) * 100).toFixed(
                                              2,
                                            )}
                                            %
                                          </td>
                                        </tr>
                                      ),
                                    )}
                                  </tbody>
                                </table>
                              </div>
                            )}
                            <h3>What to do with this finding</h3>
                            <p>{f.recommendation}</p>
                            <p className="e-source-note">{f.score_effect}</p>
                            <a
                              href="/fixtures/adult-report.html"
                              target="_blank"
                              rel="noreferrer"
                            >
                              Read the full stored report ↗
                            </a>
                          </div>
                        )}
                      </article>
                    ))}
                  </div>
                ) : (
                  <>
                    <div className="e-record-tools">
                      <label>
                        Find a record
                        <input
                          aria-label="Find an edition record"
                          placeholder="e.g. A019"
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                      </label>
                      <label>
                        Comparison status
                        <select
                          value={filter}
                          onChange={(e) => {
                            setFilter(e.target.value);
                            const match = records.find(
                              (x) =>
                                e.target.value === "all" ||
                                x.status === e.target.value,
                            );
                            if (match) setRecord(match.id);
                          }}
                        >
                          <option value="all">All 20 records</option>
                          <option value="violated">Discrepancy</option>
                          <option value="conflicting_evidence">Conflict</option>
                          <option value="satisfied">Agreement</option>
                        </select>
                      </label>
                    </div>
                    <div className="e-record-index">
                      {results.map((x) => (
                        <button
                          className={record === x.id ? "active" : ""}
                          key={x.id}
                          onClick={() => {
                            setRecord(x.id);
                            setExpanded(x.id);
                          }}
                        >
                          {x.id}
                          <small>{statusLabel(x.status)}</small>
                        </button>
                      ))}
                      {!results.length && (
                        <p>
                          No matching records. Clear the search or change the
                          status.
                        </p>
                      )}
                    </div>
                    <article className="e-record-story">
                      <div className="e-record-heading">
                        <h2>
                          {r.id}: {statusLabel(r.status).toLowerCase()}
                        </h2>
                        <span>REVENUE / INR / FY2025</span>
                      </div>
                      <div className="e-story-grid">
                        <aside className="e-margin">
                          <span>ORIGINAL RECORD</span>
                          <b className="e-record-money">₹{money(r.revenue)}</b>
                          <small>records.csv / {r.entity}</small>
                          <p>
                            Cutoff: 1 January 2026
                            <br />
                            Decimal tolerance: 0<br />
                            Authority: not declared
                          </p>
                          <label>
                            Separate review
                            <select
                              value={review[r.id] || "unreviewed"}
                              onChange={(e) =>
                                setReview({ ...review, [r.id]: e.target.value })
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
                          <p>
                            Simulated disposition; analytical evidence stays
                            unchanged.
                          </p>
                        </aside>
                        <div className="e-reading">
                          <p>
                            {r.status === "conflicting_evidence"
                              ? "Two eligible PDFs report different values. One agreeing document is insufficient to establish an unambiguous result."
                              : r.status === "violated"
                                ? "The record and eligible document disagree by a factor of ten. Review the literal source and declared extraction before deciding which value to retain."
                                : "The eligible document agrees with the structured revenue under the declared decimal rule."}
                          </p>
                          {r.documents.map((d, i) => (
                            <section className="e-source-excerpt" key={d.file}>
                              <span>SOURCE {i + 1} / PHYSICAL PAGE 1</span>
                              <h3>{d.file}</h3>
                              <p className="e-doc-value">
                                ₹{money(documentValue(d.text))}
                              </p>
                              <blockquote>{d.text}</blockquote>
                              <a
                                href={`/fixtures/${d.file}`}
                                target="_blank"
                                rel="noreferrer"
                              >
                                Read the original synthetic PDF{" "}
                                <ArrowUpRight size={14} />
                              </a>
                            </section>
                          ))}
                          <p className="e-source-note">
                            Recipe: finance / table_field / Revenue /
                            Metric–Period–Value headers / lines strategy. Entity
                            and period context match; supplied availability
                            precedes cutoff.
                          </p>
                        </div>
                      </div>
                    </article>
                  </>
                )}
              </>
            ) : chapter === "method" ? (
              <>
                <h1 className="e-chapter-title">
                  What this review
                  <br />
                  can tell you.
                </h1>
                <div className="e-method-list">
                  {principles.map(([title, text], i) => (
                    <article key={title}>
                      <span>{String(i + 1).padStart(2, "0")}</span>
                      <div>
                        <h2>{title}</h2>
                        <p>{text}</p>
                      </div>
                    </article>
                  ))}
                </div>
                <details>
                  <summary>Explore the implemented capability map</summary>
                  {capabilities.map(([id, title, text]) => (
                    <p key={id}>
                      <b>
                        {id} / {title}
                      </b>
                      <br />
                      {text}
                    </p>
                  ))}
                  <p>
                    M8 audio deferred. Classification and M9 are the interactive
                    setup examples in this lab.
                  </p>
                </details>
              </>
            ) : (
              <>
                <h1 className="e-chapter-title">
                  An investigation
                  <br />
                  you can carry forward.
                </h1>
                <p className="e-chapter-intro">
                  Existing artifacts preserve the completed analysis. Opening or
                  downloading these copies never runs another analysis.
                </p>
                <div className="e-artifacts">
                  <a
                    href={fixtureLink(family, "html")}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <span>01 / READ</span>
                    <h2>Standalone HTML</h2>
                    <p>The repository’s canonical fixture report.</p>
                    <ArrowUpRight size={24} />
                  </a>
                  <a href={fixtureLink(family, "json")} download>
                    <span>02 / INSPECT</span>
                    <h2>
                      {family === "connected"
                        ? "Strict result JSON"
                        : "Validation summary JSON"}
                    </h2>
                    <p>
                      {family === "connected"
                        ? "Original M9 public result, with opaque references."
                        : "Stored Adult summary, with the lab’s labeled source projection."}
                    </p>
                    <Download size={24} />
                  </a>
                  {family === "connected" && (
                    <a href={fixtureLink(family, "pdf")} download>
                      <span>03 / SHARE</span>
                      <h2>Existing PDF</h2>
                      <p>
                        Previously generated from canonical HTML. No conversion
                        runs here.
                      </p>
                      <Download size={24} />
                    </a>
                  )}
                  <button
                    onClick={() =>
                      download("prototype-edition-review.json", {
                        prototype: true,
                        dispositions: review,
                      })
                    }
                  >
                    <span>04 / REVIEW</span>
                    <h2>Separate review snapshot</h2>
                    <p>
                      Simulated reviewer decisions. Independent of analytical
                      evidence.
                    </p>
                    <Download size={24} />
                  </button>
                </div>
                <div className="e-colophon">
                  <h3>Disclosure & provenance</h3>
                  <p>
                    The public Adult corpus and synthetic M9 fixture are copied
                    into this disposable lab. Production portable reports omit
                    source content by default; exact local disclosure requires
                    explicit authorization. The prototype does not provide a
                    private manifest or a real source resolver.
                  </p>
                  <p>
                    Sources: validation/results/validation_summary.json;
                    validation/m9/results/reports/final/bounded.json. Original
                    reports remain unchanged.
                  </p>
                </div>
              </>
            )}
            <div className="e-next">
              <span>KEEP READING</span>
              <button
                onClick={() =>
                  setChapter(
                    chapter === "conclusions"
                      ? "evidence"
                      : chapter === "evidence"
                        ? "method"
                        : chapter === "method"
                          ? "export"
                          : "conclusions",
                  )
                }
              >
                {chapter === "conclusions"
                  ? "The evidence"
                  : chapter === "evidence"
                    ? "Methods & limits"
                    : chapter === "method"
                      ? "The artifacts"
                      : "Return to conclusions"}{" "}
                <ArrowRight size={20} />
              </button>
            </div>
          </main>
        </>
      )}
      <footer className="e-footer">
        <span>NUMEK / DECISION EDITION</span>
        <span>Evidence with a readable argument. Fixture prototype.</span>
        <span>04</span>
      </footer>
    </div>
  );
}
