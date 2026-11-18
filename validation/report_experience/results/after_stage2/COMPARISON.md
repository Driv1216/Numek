# Report Experience — before versus after_stage2

| Case | Analysis JSON identical | Pages before (canonical / app) | Pages after (focused / complete) | PDF s before (canonical) → focused | Peak PDF RSS before → focused | HTML before → after (focused) | Pages < 40% fill after (focused, excl. last) | Finding titles in PDF (focused) |
|---|---|---|---|---|---|---|---|---|
| german_credit | yes | 16 / 14 | 14 / 15 | 0.6552 → 0.5724 | 110 MiB → 101 MiB | 43,430 → 59,420 | 10 | 2/2 |
| bank_full | yes | 17 / 15 | 15 / 16 | 0.7222 → 0.7558 | 111 MiB → 105 MiB | 46,363 → 64,009 | — | 3/3 |
| bank_full_declared | yes | 19 / 17 | 17 / 18 | 0.8395 → 0.6959 | 115 MiB → 109 MiB | 51,774 → 69,417 | — | 3/3 |
| german_unlabeled | yes | 13 / — | 10 / 14 | 0.6871 → 0.4959 | 106 MiB → 96 MiB | 40,211 → 63,748 | 6 | 2/2 |
| mutation_strong_leakage | yes | 20 / — | 18 / 19 | 0.8126 → 0.7324 | 113 MiB → 107 MiB | 50,789 → 68,001 | — | 4/4 |
| mutation_feature_missingness_100 | yes | 23 / — | 21 / 21 | 0.9938 → 0.9078 | 115 MiB → 111 MiB | 55,008 → 75,281 | — | 6/6 |
| mutation_duplicates | yes | 20 / — | 18 / 19 | 0.8675 → 1.1165 | 113 MiB → 105 MiB | 51,029 → 66,900 | — | 5/5 |
| wide_200 | yes | 27 / 26 | 10 / 30 | 2.3185 → 0.4001 | 221 MiB → 93 MiB | 96,221 → 125,687 | — | 0/0 |
| wide_1000 | yes | 92 / 91 | 10 / 118 | 10.7212 → 0.4636 | 734 MiB → 94 MiB | 370,061 → 494,484 | — | 0/0 |
| wide_5000 | yes | 417 / 416 | 10 / 560 | 50.6401 → 0.5007 | 2,362 MiB → 97 MiB | 1,751,508 → 2,370,632 | — | 0/0 |
| wide_flagged_1000 | yes | 128 / 126 | 26 / 143 | 11.0017 → 1.1603 | 837 MiB → 131 MiB | 460,351 → 639,732 | 19 | 4/4 |
| tall_1m | yes | 12 / — | 12 / 12 | 0.5021 → 0.4664 | 101 MiB → 96 MiB | 35,549 → 46,193 | — | 1/1 |
| bike_hour | yes | 27 / — | 18 / 29 | 1.4854 → 0.8258 | 134 MiB → 111 MiB | 76,059 → 114,329 | — | 3/3 |
| m3_scene | yes | 11 / — | 11 / 11 | 0.4315 → 0.3895 | 101 MiB → 101 MiB | 26,739 → 26,745 | — | 2/2 |

Analysis JSON mismatches: none.
