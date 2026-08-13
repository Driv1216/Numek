This is a much better piece of work than what came before it — and it fixes the two biggest holes I flagged. But there's a process problem sitting in the middle of it that's worth catching before Codex builds it.

**What it gets right, specifically:**

The three-group, no-preselection target list is the correct synthesis of the earlier disagreement. It solves the anchoring-bias problem I raised about GPT's "we detected X, click confirm" card — there's no confident recommendation to rubber-stamp, just a friendlier ordering with the riskiest column types (single-class, many-value, continuous, identifier-like) walled off behind an explicit checkbox. It also directly answers your original "conflict of interest" worry — nothing is chosen for anyone, so a stakeholder who genuinely wants to predict something unusual still can, they just have to say so on purpose.

The narrative model is the right shape too. Deterministic templates instead of free-form generated prose was exactly the guardrail I said this needed — a wrong templated sentence is a bug you can find and fix, a wrong freely-generated sentence is a new failure mode every time. Keeping `evidence_score` additive and leaving `overall` untouched means none of this touches the thing that actually has to stay trustworthy.

**Where I'd stop it before it ships as one unit: this bundles decisions that don't carry the same risk, and Numek's own rule says not to do that.**

Target-list grouping is genuinely a UX fix with a small, testable heuristic underneath it. Report restructuring into a "layered hybrid" — decision-summary-first, evidence-after — is a different thing: it's resolving the report-tone question that's still sitting open and undecided. This spec just proceeds as if that's settled. Maybe you already made that call in a conversation I'm not seeing. If not, this document is quietly making a positioning decision (moving toward executive-evidence-pack framing) inside what reads like an implementation ticket, not a proposal asking for that decision.

I'd split it: greenlight the target-grouping change and the report bug fixes (title, pagination, dev-speak, appendix layout) as one pass. Treat the narrative/reordering model as its own decision with its own yes, even though the deterministic-template design is the right way to build it once you say go.

**Two things in the mechanics I'd want nailed down before Codex writes code:**

The outcome lexicon includes words like "risk," "class," "result," and "response" — these aren't just outcome signals, they're common *feature* names too. A lending dataset could easily have `risk_score` as an input feature feeding a prediction of `default`, and this lexicon would rank the feature above the actual target. The spec doesn't say whether matching is whole-column-name, whole-word-after-split, or substring — that ambiguity is exactly where false positives will come from, and it needs to be pinned down, not left to whatever's convenient during implementation.

The classification-shaped threshold — `min(20, floor(labeled_rows/2))` — is a new heuristic boundary with no stated reasoning for why 20 or why half the rows. It doesn't touch scoring, so it's lower stakes than the leakage heuristic, but it's still a number someone picked, and the test plan should show it was checked against something other than intuition.

**One gap in the acceptance plan:** the ambiguous-schema cases (`approved`/`defaulted_90d`/`risk_grade`, the Adult fallback) are only covered at the unit-test level. The final visual walkthrough is Titanic and Heart only — the two datasets where the target is spelled out in the column name. That's the easy case again. If the whole point of this change is making the shortlist less confusing for the non-obvious case, someone should actually look at what the grouped list renders for an ambiguous dataset, not just assert the code sorted it correctly.

So: good design, real improvement, don't let the report-tone call ride in for free inside it.