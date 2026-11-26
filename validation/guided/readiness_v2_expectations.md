# Stage 6C (J3): expected results, registered before running

Written 2026-11-25, before any 6C code was run on these cases. The expectations come from the known properties of the
public datasets (UCI Energy efficiency; scikit-learn Linnerud), not from DataTrust output.

## Rules (from the approved plan, §J3)

**Complete-case coverage**
- The share of rows in which every quantitative-geometry feature is finite.
- Finding `limited_complete_case_coverage`: Low below 80%, Moderate below 50%.

**Redundant quantitative features**
- Pairs of quantitative-geometry features that are exact duplicates, or have |Pearson r| ≥ 0.98.
- A pair qualifies only with at least 100 rows of pairwise finite overlap and at least 10 distinct values per column in that overlap.
- Finding `redundant_quantitative_features`: Low, worded "may be intended", never a defect.

**Bounded pair search**
- At most 64 features (2,016 pairs) and 2e8 row work (`DependencyLimits`).
- Order: declared quantitative features first, then source order.
- Beyond the budget the status is `bounded`, and the number of unsearched pairs is disclosed.

## Expected results

| Case | Complete-case coverage | Redundancy | Expected findings |
|---|---|---|---|
| energy_clustering | 768 of 768 rows (100%) | relative_compactness vs surface_area (\|r\| ≈ 0.99 in the UCI data). Other pairs are excluded: fewer than 10 distinct values, or \|r\| < 0.98 | `redundant_quantitative_features` (1 pair); no coverage finding |
| energy_anomaly | as above | as above | as above |
| linnerud_clustering | 20 of 20 rows (100%) | no pair evaluated: 20 rows is below the 100-row overlap gate | none from 6C |
| linnerud_anomaly | as above | as above | none from 6C |

The existing scale-ratio finding is unchanged in all four cases.

## Planted fixtures (the tests)

- **Coverage:** planted missing values give coverage of 90% (no finding), 70% (Low) and 40% (Moderate).
- **Redundancy:** an exact duplicate column and a near-collinear column (r ≈ 0.995) are found. A column with r ≈ 0.9 is not.
- **Budget:** 70 features hit the 64-feature limit; the status is `bounded` and unsearched pairs are counted.
