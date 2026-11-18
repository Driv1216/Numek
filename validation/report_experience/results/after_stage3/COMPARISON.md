# Report Experience — after_stage2 versus after_stage3

| Case | Analysis JSON identical | Pages before (canonical / app) | Pages after (focused / complete) | PDF s before (canonical) → focused | Peak PDF RSS before → focused | HTML before → after (focused) | Pages < 40% fill after (focused, excl. last) | Finding titles in PDF (focused) |
|---|---|---|---|---|---|---|---|---|
| german_credit | yes | 14 / — | 16 / — | 0.5724 → 0.8898 | 101 MiB → 112 MiB | 59,420 → 89,775 | 12 | 2/2 |
| bank_full | yes | 15 / — | 18 / — | 0.7558 → 0.9765 | 105 MiB → 114 MiB | 64,009 → 97,284 | — | 3/3 |
| bank_full_declared | yes | 17 / — | 20 / — | 0.6959 → 0.9751 | 109 MiB → 118 MiB | 69,417 → 102,692 | — | 3/3 |
| german_unlabeled | yes | 10 / — | 12 / — | 0.4959 → 0.6277 | 96 MiB → 102 MiB | 63,748 → 88,962 | 6 | 2/2 |
| mutation_strong_leakage | yes | 18 / — | 21 / — | 0.7324 → 1.0486 | 107 MiB → 115 MiB | 68,001 → 100,330 | 14 | 4/4 |
| mutation_feature_missingness_100 | yes | 21 / — | 23 / — | 0.9078 → 1.0624 | 111 MiB → 119 MiB | 75,281 → 108,506 | 15 | 6/6 |
| mutation_duplicates | yes | 18 / — | 20 / — | 1.1165 → 1.0339 | 105 MiB → 116 MiB | 66,900 → 99,299 | — | 5/5 |
| wide_200 | yes | 10 / — | 13 / — | 0.4001 → 0.6475 | 93 MiB → 103 MiB | 125,687 → 156,830 | 9 | 0/0 |
| wide_1000 | yes | 10 / — | 13 / — | 0.4636 → 0.6589 | 94 MiB → 104 MiB | 494,484 → 525,634 | 9 | 0/0 |
| wide_5000 | yes | 10 / — | 13 / — | 0.5007 → 0.7208 | 97 MiB → 106 MiB | 2,370,632 → 2,401,784 | 9 | 0/0 |
| wide_flagged_1000 | yes | 26 / — | 29 / — | 1.1603 → 1.5725 | 131 MiB → 147 MiB | 639,732 → 676,552 | 19 | 4/4 |
| tall_1m | yes | 12 / — | 15 / — | 0.4664 → 0.6912 | 96 MiB → 105 MiB | 46,193 → 78,190 | 8, 11 | 1/1 |
| bike_hour | yes | 18 / — | 21 / — | 0.8258 → 1.0086 | 111 MiB → 119 MiB | 114,329 → 143,021 | 12 | 3/3 |

Analysis JSON mismatches: none.
