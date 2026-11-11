# WS3 benchmark results (ws3_context_v1)

Definition sha256 `c4bed25f91e83e47a778dfe6a169398261e0e1428662a837573d87b096abf6f7`, frozen before evaluation.

- Cases: 29; agreeing with their frozen expectation: 29; disagreeing: none.
- Dependency search, positives: 4 of 4 detected; missed: none.
- Dependency search, negatives: 0 false flags of 5; none.
- Expected misses (true leaks the gates cannot detect): dep_noisy_copy missed.
- Abstentions: dep_small_sample, cand_999_rare. Unsearched features across dependency cases: 21.

Families are mutations of three base datasets; they are not independent samples. Results establish behaviour on these constructed cases only, not external validity.

| Case | Family | Kind | Class | Outcome | Agrees |
|---|---|---|---|---|---|
| dep_copy_renamed | german | dependency | positive | detected | yes |
| dep_numeric_reencoding | german | dependency | positive | detected | yes |
| dep_categorical_proxy | adult | dependency | positive | detected | yes |
| dep_quantitative_separator | bank | dependency | positive | detected | yes |
| dep_noisy_copy | german | dependency | expected_miss | missed | yes |
| dep_outcome_like_name | german | dependency | negative | clean | yes |
| dep_identifier | adult | dependency | negative | clean | yes |
| dep_raw_bank | bank | dependency | negative | clean | yes |
| dep_raw_adult | adult | dependency | negative | clean | yes |
| dep_raw_german | german | dependency | negative | clean | yes |
| dep_small_sample | german | dependency | abstention | abstained | yes |
| dep_declared_available | german | availability | negative | agrees | yes |
| dep_declared_unavailable | german | availability | positive | agrees | yes |
| avail_duration_declared | bank | availability | positive | agrees | yes |
| avail_duration_undeclared | bank | availability | negative | agrees | yes |
| cand_bank | bank | candidates | positive | agrees | yes |
| cand_real_minus_one | german | candidates | negative | agrees | yes |
| cand_999_outside | german | candidates | positive | agrees | yes |
| cand_999_rare | german | candidates | abstention | abstained | yes |
| decl_pdays | bank | declaration | positive | agrees | yes |
| decl_poutcome | bank | declaration | positive | agrees | yes |
| decl_typo | bank | declaration | positive | agrees | yes |
| ba_filter_keys | german | before_after | positive | agrees | yes |
| ba_filter_no_keys | german | before_after | positive | agrees | yes |
| ba_dedup | bank | before_after | positive | agrees | yes |
| ba_undeclared_drop | german | before_after | positive | agrees | yes |
| ba_incomplete_impute | german | before_after | positive | agrees | yes |
| ba_undeclared_encoding | bank | before_after | positive | agrees | yes |
| ba_declared_not_done | german | before_after | positive | agrees | yes |
