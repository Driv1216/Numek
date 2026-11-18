# Report Experience — before versus after_stage8_rule

| Case | Analysis JSON identical | Pages before (canonical / app) | Pages after (focused / complete) | PDF s before (canonical) → focused | Peak PDF RSS before → focused | HTML before → after (focused) | Pages < 40% fill after (focused, excl. last) | Finding titles in PDF (focused) |
|---|---|---|---|---|---|---|---|---|
| german_credit | yes | 16 / 14 | 16 / 17 | 0.6552 → 0.8384 | 110 MiB → 110 MiB | 43,430 → 91,433 | 12 | 2/2 |
| bank_full | yes | 17 / 15 | 18 / 19 | 0.7222 → 0.9808 | 111 MiB → 114 MiB | 46,363 → 98,941 | — | 3/3 |
| bank_full_declared | yes | 19 / 17 | 20 / 21 | 0.8395 → 0.982 | 115 MiB → 118 MiB | 51,774 → 104,350 | — | 3/3 |
| german_unlabeled | yes | 13 / — | 12 / 16 | 0.6871 → 0.6488 | 106 MiB → 102 MiB | 40,211 → 90,641 | 6 | 2/2 |
| mutation_strong_leakage | yes | 20 / — | 21 / 22 | 0.8126 → 1.0853 | 113 MiB → 115 MiB | 50,789 → 102,064 | 14 | 4/4 |
| mutation_feature_missingness_100 | yes | 23 / — | 23 / 23 | 0.9938 → 1.0967 | 115 MiB → 119 MiB | 55,008 → 110,492 | 15 | 6/6 |
| mutation_duplicates | yes | 20 / — | 20 / 21 | 0.8675 → 1.0567 | 113 MiB → 116 MiB | 51,029 → 100,899 | — | 5/5 |
| wide_200 | yes | 27 / 26 | 14 / 33 | 2.3185 → 0.7021 | 221 MiB → 104 MiB | 96,221 → 157,964 | 7, 10 | 0/0 |
| wide_1000 | yes | 92 / 91 | 14 / 122 | 10.7212 → 0.6838 | 734 MiB → 104 MiB | 370,061 → 526,768 | 7, 10 | 0/0 |
| wide_5000 | yes | 417 / 416 | 14 / 564 | 50.6401 → 0.7367 | 2,362 MiB → 107 MiB | 1,751,508 → 2,402,918 | 7, 10 | 0/0 |
| wide_flagged_1000 | yes | 128 / 126 | 29 / 146 | 11.0017 → 1.5829 | 837 MiB → 147 MiB | 460,351 → 678,758 | 19 | 4/4 |
| tall_1m | yes | 12 / — | 15 / 15 | 0.5021 → 0.6911 | 101 MiB → 105 MiB | 35,549 → 79,324 | 8, 11 | 1/1 |
| bike_hour | yes | 27 / — | 21 / 33 | 1.4854 → 1.0489 | 134 MiB → 120 MiB | 76,059 → 144,746 | 12 | 3/3 |
| m3_scene | yes | 11 / — | 14 / 20 | 0.4315 → 0.6313 | 101 MiB → 110 MiB | 26,739 → 98,872 | 10 | 2/2 |
| m4_contaminated | yes | 4 / — | 6 / 6 | 0.2091 → 0.3832 | 88 MiB → 95 MiB | 11,189 → 40,228 | — | 1/1 |
| m4_wide | yes | 4 / — | 6 / 9 | 0.2544 → 0.3791 | 87 MiB → 93 MiB | 11,146 → 51,761 | — | 2/2 |
| m4_long_headers | yes | 5 / — | 6 / 6 | 0.2048 → 0.3173 | 85 MiB → 90 MiB | 10,298 → 35,468 | — | 2/2 |

Analysis JSON mismatches: none.
