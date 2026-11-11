import adult from "./fixtures/classification.json";
import connected from "./fixtures/connected.json";
export const classification = adult;
export const findings = adult.risks;
export const records = connected;
export type RecordEvidence = (typeof records)[number];
export type Finding = (typeof findings)[number];
export type Family = "classification" | "connected";
export const money = (value: string | number) =>
  new Intl.NumberFormat("en-IN").format(Number(value));
export const statusLabel = (s: string) =>
  s === "satisfied"
    ? "Agreement"
    : s === "violated"
      ? "Discrepancy"
      : "Conflict";
export const documentValue = (text: string) =>
  text.match(/Revenue FY2025 (\d+)/)?.[1] ?? "Unavailable";
export const capabilities = [
  [
    "M1",
    "Profiling",
    "Target-free missingness, repetition and parsing evidence. No overall score.",
  ],
  [
    "M2",
    "Regression",
    "Finite outputs, constraints and bounded arithmetic relationships. No score.",
  ],
  [
    "M3",
    "Annotations & advanced tabular",
    "Unknown expectations, multilabel indicators, multiple outputs and explicit feature roles.",
  ],
  [
    "M4",
    "Comparisons & scale",
    "Split/version effects and bounded DuckDB investigations. No composite verdict.",
  ],
  [
    "M5",
    "Temporal",
    "Declared clocks, schedules, revisions, availability and supplied evaluation plans. No backtest.",
  ],
  [
    "M6",
    "Text",
    "Annotations, conversations, retrieval integrity and bounded local similarity candidates.",
  ],
  [
    "M7",
    "Images",
    "Integrity, annotations, repetition, splits and explicit version comparisons. No quality score.",
  ],
  [
    "M9",
    "Connected evidence",
    "Explicit links, native PDF/DOCX recipes, precision-safe reconciliation and scoped candidates.",
  ],
];
export const principles = [
  [
    "Scoring has a scope",
    "Adult classification: sub-score mean 89.15, capped at 69 by target balance 47.86. The score is a heuristic interpretation, not model performance or a confidence estimate. M9 has no overall score.",
  ],
  [
    "Coverage is evidence",
    "The shared M9 decimal rule covers 20 records and 21 candidate occurrences, with 0 incomplete records. This does not establish complete document layout assurance or general claim correctness.",
  ],
  [
    "Source access stays local",
    "The product resolves exact source hashes and locators through a protected private manifest. These prototypes expose only copied synthetic fixture PDFs. Opening evidence does not authorize its inclusion in portable reports.",
  ],
  [
    "Reviews are independent",
    "Confirm, dismiss and unresolved are reviewer dispositions. They never rewrite the analytical finding. Prototype dispositions live in memory and reset on reload.",
  ],
  [
    "Execution is bounded",
    "Production uses a local Flask UI and supervised local workers. Planned search limits, omitted presentation detail and unexpected failures are different states. No real analysis runs here.",
  ],
  [
    "Know the limits",
    "No general truth verification, OCR, automatic cleaning, cloud inference or M8 audio. Optional semantic models have narrow qualification and can abstain.",
  ],
];
export function download(name: string, value: unknown) {
  const blob = new Blob([JSON.stringify(value, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
export function fixtureLink(family: Family, format: string) {
  return family === "connected"
    ? `/fixtures/m9-report.${format}`
    : `/fixtures/adult-${format === "json" ? "summary.json" : "report.html"}`;
}
export function exportConfig(
  family: Family,
  target: string,
  extra: Record<string, unknown> = {},
) {
  download("prototype-configuration.json", {
    prototype: true,
    executed: false,
    fixture: family,
    task:
      family === "classification"
        ? { kind: "classification", targets: [target] }
        : {
            method: "decimal",
            field: "revenue",
            unit: "INR",
            tolerance: "0",
            context: ["entity", "period"],
            cardinality: "one_to_many",
          },
    ...extra,
  });
}
