# M5 narrow source-review correction pass — 2026-10-11

Status: correction pass complete. This record concerns current-source confirmation, bounded corrections and newly executed focused checks. It does not initiate the M5 understanding pass or technical sign-off.

## Confirmed and rejected interpretations

| Finding | Source confirmation and resulting behavior |
|---|---|
| Declared purge skipped with no chronology | Confirmed. Origin purge now uses global boundaries when chronology is none; within-entity chronology keeps its existing scope. Missing usable pairs or incompatible elapsed semantics disclose blocked requirements. Label-gap unassessable boundaries are also explicit. |
| Asymmetric label intersections | Confirmed. A narrow distinct training-point relation plus ASOF lookup handles evaluation intervals intersecting training points, as well as the existing reverse direction. Interval starts are inclusive and ends exclusive; global and within-entity scopes are retained. Each evaluation row counts once. Missing entity keys are excluded from within-entity label matching. |
| Disjoint-label declaration without clocks | Confirmed. TemporalFoldSpec rejects disjoint_labels without both label endpoint declarations. Equal endpoints remain the existing representation of point labels. |
| Missing opportunities mislabeled as gap intervals | Confirmed. Supplied missing-opportunity counts/point witnesses remain; compressed-gap count and longest-gap slots are null with explicit disclosure. No new compressed-calendar algorithm was added. Fixed/civil compression remains unchanged. |
| History-only past-observation restrictions | Confirmed. The existing restriction uses explicit history cutoffs even without an availability rule; identical feature/cutoff bindings avoid duplicate checks. Unknown availability is not inferred. |
| Optional rollback stale selection/SQL state | Confirmed. Rollback restores relation caches and selected-series counters/set, removes new intermediate tables and discards uncommitted evidence. New work charges are disclosed in failed-stage evidence. The suggestion to refund observation-visits/comparisons is rejected: failed work has consumed budget, and refunds could bypass limits. |
| Per-source-only series cap | Confirmed against the approved job budget. The cap now applies to the sum of source-qualified observed/expected series, including absent supplied entities. Existing per-source safeguards remain. |
| Detailed-series omitted from main behavior topic | Confirmed. behavior_series is now included and its aggregate summary prioritized before detailed window rows; per-series details retain appendix/JSON placement and existing bounds. |
| Boundary lookback should be reconstructed | No faulty reconstruction claim was substantiated: the code already stated boundary-only support. The algorithm is retained, and evidence/docs now explicitly exclude internal continuity and feature-specific point-in-time assurance. |

## Exact runtime edits

| File | Changed functions/data |
|---|---|
| `src/datatrust/temporal.py` | `execute` (lines 59–143) |
| `src/datatrust/temporal_contracts.py` | `TemporalFoldSpec.__post_init__` (lines 312–328) |
| `src/datatrust/temporal_evaluation.py` | `interval_union` (lines 7–14), `evaluation` (lines 17–127) |
| `src/datatrust/temporal_diagnostics.py` | `Evidence.optional` (lines 33–56), `continuity` (lines 169–240) |
| `src/datatrust/temporal_availability.py` | `past_observation` (lines 15–22), `availability` (lines 25–57) |
| `src/datatrust/temporal_behavior.py` | `behavior` (lines 185–242) — optional-context arguments only; diagnostic mathematics unchanged |
| `src/datatrust/temporal_presentation.py` | `report_view` (lines 37–107); `TOPICS` family membership |

Directly affected tests: `tests/m5/test_truth_tables.py`, `tests/m5/test_resources_and_semantics.py`, `tests/m5/test_interfaces_behavior.py`. Methodology descriptions: `docs/M5_TEMPORAL_RELIABILITY.md`. This new pass record preserves earlier ledgers unchanged. No M1–M4 contracts, algorithms, source adapters, supervisor, CLI/browser lifecycle, renderer or PDF converter were edited.

## New verification and reused evidence

The first invocation failed during collection because it omitted PYTHONPATH; no tests executed. The corrected invocation ran the same selected set: **22 passed in 1.95 seconds**. There was no implementation-test failure and no subsequent rerun, broader suite, validator, benchmark, browser run or PDF conversion.

The selected checks cover independent origin gaps/blocked boundaries, bidirectional half-open point/interval intersections and entity scope, strict declarations, supplied opportunity reporting, history-only restrictions, optional state cleanup/continuation and fatal allocation behavior, combined observed/expected limits, main report inclusion, and relevant fixed/civil/behavioral/multivariate/annotation/requested-scope regressions.

The existing M5 ledger records a prior 40-test M5 run, a consolidated run with fixture failures and its 26-test parity/M4 follow-up, plus historical corpus/presentation/capacity work. Those outcomes are not repeated or relabeled here. Hash matches below delimit unchanged source evidence that remains usable. Changed analysis/report behavior is supported only by this pass’s focused checks; old PDF page-count/visual evidence does not certify the new projection. M4’s earlier execution-verified closure and later source-only corrections remain distinct.

## Remaining concrete limitations

- Supplied-calendar compressed gaps/longest gaps remain explicitly unavailable; point missing-opportunity witnesses are retained.
- Lookback support remains observed-boundary evidence pooled across measurements, not feature-specific point-in-time reconstruction or continuous coverage.
- Work visits/comparisons remain charged after optional failure; rollback restores uncommitted evidence, newly created tables, relation caches and selected-series state. It is not a general transaction for arbitrary existing-table mutations.
- Existing output row/detail bounds remain; no new PDF layout or capacity guarantee is made.
- M4 execution-verified history and source-only corrections retain their original status.

## Evidence ledger (exact commands and hashes)

```json
{
  "generated_at_utc": "2026-10-10T23:46:58.645743+00:00",
  "scope": "Narrow correction of four required and four secondary source-review findings; no M5 understanding pass.",
  "verification_policy": "agents/skills/verify/skills.md",
  "commands": [
    {
      "command": ".venv/bin/python -m pytest -q tests/m5/test_truth_tables.py::test_origin_gap_without_chronology tests/m5/test_truth_tables.py::test_symmetric_point_interval_labels tests/m5/test_truth_tables.py::test_interval_label_purge_and_point_boundaries tests/m5/test_truth_tables.py::test_history_only_past_observation tests/m5/test_truth_tables.py::test_optional_atomic_rollback_and_required_failure tests/m5/test_truth_tables.py::test_missing_runs_break_and_seasonal_support tests/m5/test_truth_tables.py::test_civil_categorical_phase_matching tests/m5/test_truth_tables.py::test_multivariate_and_annotation_windows tests/m5/test_truth_tables.py::test_requested_series_precedes_automatic_search_across_sources tests/m5/test_truth_tables.py::test_supplied_calendar_absent_entity_and_timeline_domain tests/m5/test_resources_and_semantics.py::test_supplied_event_opportunities_not_outages tests/m5/test_resources_and_semantics.py::test_combined_observed_and_expected_series_limit tests/m5/test_resources_and_semantics.py::test_contract_strictness_and_override tests/m5/test_resources_and_semantics.py::test_evaluation_half_open_membership tests/m5/test_resources_and_semantics.py::test_civil_schedule_dst_and_absent_entity tests/m5/test_temporal.py::test_bound_timing_and_unknown tests/m5/test_temporal.py::test_fixed_gaps_duplicates_and_missing tests/m5/test_interfaces_behavior.py::test_detailed_series_in_main_behavior_report tests/m5/test_interfaces_behavior.py::test_behavior_zero_reference_and_runs",
      "exit_code": 4,
      "outcome": "Collection failed: datatrust not installed/importable without source path. No test cases executed."
    },
    {
      "command": "PYTHONPATH=src .venv/bin/python -m pytest -q tests/m5/test_truth_tables.py::test_origin_gap_without_chronology tests/m5/test_truth_tables.py::test_symmetric_point_interval_labels tests/m5/test_truth_tables.py::test_interval_label_purge_and_point_boundaries tests/m5/test_truth_tables.py::test_history_only_past_observation tests/m5/test_truth_tables.py::test_optional_atomic_rollback_and_required_failure tests/m5/test_truth_tables.py::test_missing_runs_break_and_seasonal_support tests/m5/test_truth_tables.py::test_civil_categorical_phase_matching tests/m5/test_truth_tables.py::test_multivariate_and_annotation_windows tests/m5/test_truth_tables.py::test_requested_series_precedes_automatic_search_across_sources tests/m5/test_truth_tables.py::test_supplied_calendar_absent_entity_and_timeline_domain tests/m5/test_resources_and_semantics.py::test_supplied_event_opportunities_not_outages tests/m5/test_resources_and_semantics.py::test_combined_observed_and_expected_series_limit tests/m5/test_resources_and_semantics.py::test_contract_strictness_and_override tests/m5/test_resources_and_semantics.py::test_evaluation_half_open_membership tests/m5/test_resources_and_semantics.py::test_civil_schedule_dst_and_absent_entity tests/m5/test_temporal.py::test_bound_timing_and_unknown tests/m5/test_temporal.py::test_fixed_gaps_duplicates_and_missing tests/m5/test_interfaces_behavior.py::test_detailed_series_in_main_behavior_report tests/m5/test_interfaces_behavior.py::test_behavior_zero_reference_and_runs",
      "exit_code": 0,
      "outcome": "22 passed in 1.95s",
      "scope": "19 selected functions, including four parametrized point/interval/entity cases."
    }
  ],
  "source_and_test_hashes": {
    "src/datatrust/temporal.py": {
      "before_sha256": "5b227935296e94846bf2289ee906886a55d5620a97b0d1d42a444cfa6382d170",
      "after_sha256": "a13e0e89412c0aa6d98f27e1f186113126fae9ca996189bfb24471ec684729f5"
    },
    "src/datatrust/temporal_contracts.py": {
      "before_sha256": "667510e7898ccded52892357e70a53b4e5071ab1d93696a23cffc63d440184b0",
      "after_sha256": "74368bcf887ac3b0ab9b455fffd840a02d99345a479ce4bdaa4715374853946e"
    },
    "src/datatrust/temporal_diagnostics.py": {
      "before_sha256": "b94e5b5a884d000640a21baa2cdddafda5ddb63d9f95eaf1aa92a8e960216f50",
      "after_sha256": "642f904eb90652caab185786a5fb054fb4c196e1c0a4dcfbadb7d149edbf8628"
    },
    "src/datatrust/temporal_evaluation.py": {
      "before_sha256": "c3d40e2a2f9c6f6506a44869628909587bbb3ebedf058682cc9eda7e46fe55b7",
      "after_sha256": "cad5f50a520ec5645a2c17378ffbd2718250784a8313ca806633c5457992ec9b"
    },
    "src/datatrust/temporal_availability.py": {
      "before_sha256": "573edccf220f85fc26c862631309355d428a77bab6e7ddfda5349854d904656f",
      "after_sha256": "b2bd3b601003ba6a827a1d72a5de86ca209f4bba791f589387ef4a614f4f1cfa"
    },
    "src/datatrust/temporal_behavior.py": {
      "before_sha256": "c24f9c0a1d2ed0e6ec03a4d4166de3361de3ba3ac3a1c9c54ce23a2be2ff483d",
      "after_sha256": "138af129ebc55f22ea4a952dd6e5ea6d9a978a9ff5ac4dc772e82e6a32009e53"
    },
    "src/datatrust/temporal_presentation.py": {
      "before_sha256": "4a6b9030f7d7cad1b54b1da00f870edca14b4c4dc8d1182d0cd660dee83713e3",
      "after_sha256": "f94eec93cbd459a0349e056a061e3d481fc72e5804af9bf9c670272a34ed4fe1"
    },
    "tests/m5/test_truth_tables.py": {
      "before_sha256": "044de8c436d7d670c985cc865cd06916182a7182821d230676593a9e09e691f9",
      "after_sha256": "be990438f35567a0e4673133001368b7b83e874d4300dec1fe2119fe83478797"
    },
    "tests/m5/test_resources_and_semantics.py": {
      "before_sha256": "f995fb2af534b3beb66d87330331c1f0fefbe3beeb944756aa8c1e8905e20170",
      "after_sha256": "74fa1ef7c685e2fd561bbb785552c5c55be5e64804b1413114cec77877bf9cbe"
    },
    "tests/m5/test_interfaces_behavior.py": {
      "before_sha256": "a543a66e22668d5840c18d6477a7063426bdea9acd5433f892979167f22b64db",
      "after_sha256": "f181434ba0eeac7dd3340ff66b01d1c0d989040f47fd4849b6f085d680bfe4a9"
    },
    "docs/M5_TEMPORAL_RELIABILITY.md": {
      "before_sha256": "9091f11a57b9d853356c942de830d2a1200e9b0a3b379fd85082dd5488ec9b7f",
      "after_sha256": "7cb5577a0b00b0ac4cfe21a8d3b414f620c011070b12970e0d6d656e6d824baa"
    }
  },
  "test_configuration_evidence": "Explicit source/config fixtures are in the hashed test files. The successful invocation imported the current src tree via PYTHONPATH=src.",
  "historical_evidence_context": {
    "path": "validation/m5/results/evidence_ledger.json",
    "sha256": "8c68ba53345f42610de7d7849433c88f0eb62e5645596945ba9ac03f9e71fc43",
    "recorded_at": "2026-10-10T23:03:30.419052+00:00",
    "matches_for_unchanged_sources": {
      "agents/skills/verify/skills.md": "007fbef5c923e3baf9121c7bd2e5ac705a1f7cd36a582a81efbc9b16cbe833db",
      "pyproject.toml": "e2c95ed54822907f343df4f832063722ed181b0ac66286c6e557b6d71ad08589",
      "setup.py": "11cd5be223f41e8ee42d54c5694ff68d4a60eea2c34e8ad3729e0bfb4092c080",
      "src/datatrust/__init__.py": "59fdde94a281235de4cedaabf4d84587348a2b142da012d43bebdb3f5faeb01b",
      "src/datatrust/cli.py": "cbe0c82619c2a1d6d435dc03ff1463a3fb61355d8b9dc64792017719338cdf09",
      "src/datatrust/comparison.py": "0bd7ca1368602d5ef71bf14c3abc3924984ebc147297a99498a6b3cca5935fa6",
      "src/datatrust/core.py": "dab56b220032523684c67a34da61664dcd39ec3b815ddea4c70e97938783302f",
      "src/datatrust/distribution_effects.py": "46814c5669a9d6d170e5517baee6c73f90cce8ee68212e94cf9b7d977ef256a0",
      "src/datatrust/m4_worker.py": "367977db5264bf2258bebd662ca39aca2372a47e559cd40648d2e24e2d1eb458",
      "src/datatrust/renderer.py": "b721daa43f07d9f8ff4ae8256be0b1da8618dda370fc3db06495619faa6a179a",
      "src/datatrust/scalable.py": "39e59b186128a95542a25ae74cece094428727d5e792e303b0aaa6b5c61592a9",
      "src/datatrust/templates/temporal_report.html": "43392f55e693e242f93c7f3c888444f1a348498909f0eed2867da57a406a2560",
      "src/datatrust/templates/temporal_ui.html": "95fc8164be5113475f4492d378cf01342e2757af592853ed246756e68532764b",
      "src/datatrust/temporal_multivariate.py": "8094c8f7732587ed56a3d9c15963d1b56153dc38866e92616f6d22ac6f1827ca",
      "src/datatrust/temporal_normalization.py": "84c7b2dd53243df45a72d6394e33420340ac6b7c481d4a3100a91172893735c8",
      "src/datatrust/temporal_web.py": "c4e926924e569ffc2def0a9d9819e0a736b7dd41458b0737cfaa788c3193b833",
      "src/datatrust/web.py": "6228ca9a624816d8676d4625654a38b8de7f1d7e03e5f8d5904bfee7aa0cceaa",
      "src/datatrust/worker.py": "d3ce3b7cf79ef0bc3aa71e776be73348e44e9dcb75df1d1140cabdb01a8d0bac",
      "tests/m5/test_temporal.py": "b9b4219df60999607c8d1fbcdeba12369149308b12e01fee595bb401e87b17f6"
    },
    "status": "Historical evidence reused only for unchanged behavior; no repeat or retrospective relabeling. Prior presentation/page-count evidence does not verify the changed behavioral report projection."
  },
  "not_executed": [
    "full pytest suite",
    "unrelated validators",
    "public-corpus reanalysis",
    "capacity/stress benchmarks",
    "browser end-to-end checks",
    "PDF conversion/visual/page-count checks"
  ],
  "remaining_limits": [
    "Supplied-calendar compressed gaps/longest gaps remain explicitly unavailable; point missing-opportunity witnesses are retained.",
    "Lookback support remains observed-boundary evidence pooled across measurements, not feature-specific point-in-time reconstruction or continuous coverage.",
    "Work visits/comparisons remain charged after optional failure; rollback restores uncommitted evidence, newly created tables, relation caches and selected-series state. It is not a general transaction for arbitrary existing-table mutations.",
    "Existing output row/detail bounds remain; no new PDF layout or capacity guarantee is made.",
    "M4 execution-verified history and source-only corrections retain their original status."
  ]
}
```
