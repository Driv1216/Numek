import { useState } from "react";
import { Guided } from "./concepts/guided/Guided";
import { Console } from "./concepts/console/Console";
import { Workbench } from "./concepts/workbench/Workbench";
import { Edition } from "./concepts/edition/Edition";
import { Analytical } from "./concepts/analytical/Analytical";
const concepts = [
  [
    "01",
    "Guided Studio",
    "Follow a purposeful sequence, with one decision at a time.",
    "guided",
    "#eee9de",
  ],
  [
    "02",
    "Analyst Console",
    "Search, triage and inspect from a compact keyboard-first queue.",
    "console",
    "#242a31",
  ],
  [
    "03",
    "Evidence Workbench",
    "Keep records and original sources side by side in an adjustable workspace.",
    "workbench",
    "#e1e9ec",
  ],
  [
    "04",
    "Decision Edition",
    "Read an investigation as an edition, from conclusion to exact evidence.",
    "edition",
    "#e9e3d1",
  ],
  [
    "05",
    "Analytical Studio",
    "Explore populations through linked charts and inspect what the marks represent.",
    "analytical",
    "#e4ece9",
  ],
];
export function App() {
  const path = location.pathname.split("/")[1];
  const [left, setLeft] = useState("guided"),
    [right, setRight] = useState("workbench"),
    [compare, setCompare] = useState(false);
  const views: Record<string, React.ReactNode> = {
    guided: <Guided />,
    console: <Console />,
    workbench: <Workbench />,
    edition: <Edition />,
    analytical: <Analytical />,
  };
  if (views[path])
    return (
      <>
        {views[path]}
        {!new URLSearchParams(location.search).has("embed") && (
          <a className="lab-return" href="/">
            ← Design lab
          </a>
        )}
      </>
    );
  return (
    <main className="launcher">
      <header>
        <strong>NUMEK / DATATRUST</strong>
        <span>FRONTEND DESIGN LAB · 01—05</span>
      </header>
      <h1>Five ways to investigate.</h1>
      <p className="intro">
        The same evidence. Five fundamentally different ways of working with it.
        Explore the guided workflow, the finding queue, the source canvas, the
        decision report and the analytical plot.
      </p>
      <p className="intro">
        Isolated React prototypes. Local fixture interactions only.
        Classification uses verified UCI Adult evidence; connected evidence uses
        the repository’s synthetic 20-record / 21-PDF example.
      </p>
      <div className="launcher-grid">
        {concepts.map(([n, name, description, slug, color]) => (
          <article className="concept-entry" key={slug}>
            <div
              className={`mini-layout mini-${n}`}
              style={
                {
                  "--mini": color,
                  color: n === "02" ? "#fff" : "#243d43",
                } as React.CSSProperties
              }
            >
              <i />
              <b />
              <em />
            </div>
            <h2>
              {n} / {name}
            </h2>
            <p>{description}</p>
            <a href={`/${slug}`}>Open concept ↗</a>
            <a href={`/${slug}?view=new`}>Try a new analysis →</a>
          </article>
        ))}
      </div>
      <details>
        <summary>Compare two concepts side by side</summary>
        <p>
          Each frame is independently interactive. At narrow widths the frames
          stack.
        </p>
        <div className="compare-controls">
          <label>
            Left{" "}
            <select value={left} onChange={(e) => setLeft(e.target.value)}>
              {concepts.map((c) => (
                <option key={c[3]} value={c[3]}>
                  {c[1]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Right{" "}
            <select value={right} onChange={(e) => setRight(e.target.value)}>
              {concepts.map((c) => (
                <option key={c[3]} value={c[3]}>
                  {c[1]}
                </option>
              ))}
            </select>
          </label>
          <button onClick={() => setCompare(!compare)}>
            {compare ? "Close comparison" : "Load comparison"}
          </button>
        </div>
        {compare && (
          <div className="comparison">
            <iframe
              key={left}
              src={`/${left}?embed=1`}
              title={`Compare ${left}`}
            />
            <iframe
              key={right}
              src={`/${right}?embed=1`}
              title={`Compare ${right}`}
            />
          </div>
        )}
      </details>
      <footer>
        Every concept includes setup, classification, connected evidence,
        methodology and exports. Prototype review states reset on reload. No
        analytical execution or production integration.
      </footer>
    </main>
  );
}
