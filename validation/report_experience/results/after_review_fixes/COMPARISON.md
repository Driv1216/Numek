# Report Experience — before versus after_review_fixes

| Case | Analysis JSON identical | Pages before (canonical / app) | Pages after (focused / complete) | PDF s before (canonical) → focused | Peak PDF RSS before → focused | HTML before → after (focused) | Pages < 40% fill after (focused, excl. last) | Finding titles in PDF (focused) |
|---|---|---|---|---|---|---|---|---|
| german_credit | yes | 16 / 14 | 16 / 17 | 0.6552 → 0.8488 | 110 MiB → 110 MiB | 43,430 → 91,819 | 12 | 2/2 |
| bank_full | yes | 17 / 15 | 18 / 19 | 0.7222 → 1.0354 | 111 MiB → 114 MiB | 46,363 → 99,363 | — | 3/3 |
| bank_full_declared | yes | 19 / 17 | 20 / 21 | 0.8395 → 1.017 | 115 MiB → 118 MiB | 51,774 → 104,771 | — | 3/3 |
| german_unlabeled | yes | 13 / — | 13 / 16 | 0.6871 → 0.6283 | 106 MiB → 102 MiB | 40,211 → 91,363 | 6 | 2/2 |
| mutation_strong_leakage | yes | 20 / — | 21 / 22 | 0.8126 → 1.0734 | 113 MiB → 116 MiB | 50,789 → 102,451 | 14 | 4/4 |
| mutation_feature_missingness_100 | yes | 23 / — | 23 / 23 | 0.9938 → 1.0628 | 115 MiB → 119 MiB | 55,008 → 110,878 | 15 | 6/6 |
| mutation_duplicates | yes | 20 / — | 20 / 21 | 0.8675 → 1.0501 | 113 MiB → 116 MiB | 51,029 → 101,286 | — | 5/5 |
| wide_200 | yes | 27 / 26 | 14 / 33 | 2.3185 → 0.6606 | 221 MiB → 104 MiB | 96,221 → 158,454 | 7, 10 | 0/0 |
| wide_1000 | yes | 92 / 91 | 14 / 122 | 10.7212 → 0.7071 | 734 MiB → 104 MiB | 370,061 → 527,258 | 7, 10 | 0/0 |
| wide_5000 | yes | 417 / 416 | 14 / 564 | 50.6401 → 0.7406 | 2,362 MiB → 108 MiB | 1,751,508 → 2,403,408 | 7, 10 | 0/0 |
| wide_flagged_1000 | yes | 128 / 126 | 26 / 143 | 11.0017 → 1.3011 | 837 MiB → 140 MiB | 460,351 → 679,343 | 16 | 4/4 |
| tall_1m | yes | 12 / — | 15 / 15 | 0.5021 → 0.6852 | 101 MiB → 106 MiB | 35,549 → 79,718 | 8, 11 | 1/1 |
| bike_hour | yes | 27 / — | 21 / 33 | 1.4854 → 0.9992 | 134 MiB → 120 MiB | 76,059 → 145,740 | 12 | 3/3 |
| m3_scene | yes | 11 / — | 14 / 20 | 0.4315 → 0.6045 | 101 MiB → 110 MiB | 26,739 → 99,229 | 10 | 2/2 |
| m4_contaminated | yes | 4 / — | 6 / 6 | 0.2091 → 0.3804 | 88 MiB → 97 MiB | 11,189 → 40,570 | — | 1/1 |
| m4_wide | yes | 4 / — | 7 / 9 | 0.2544 → 0.5087 | 87 MiB → 105 MiB | 11,146 → 71,819 | — | 2/2 |
| m4_long_headers | yes | 5 / — | 6 / 6 | 0.2048 → 0.3272 | 85 MiB → 92 MiB | 10,298 → 35,810 | — | 2/2 |
| m5_retail | yes | 10 / — | 11 / 85 | 0.5615 → 0.8494 | 104 MiB → 125 MiB | 122,050 → 641,451 | — | 2/2 |
| m5_beijing | yes | 10 / — | 23 / 160 | 0.5389 → 1.3236 | 105 MiB → 160 MiB | 131,833 → 1,305,499 | 16 | 15/15 |
| m5_long_headers | yes | 10 / — | 10 / 806 | 0.5759 → 0.9078 | 105 MiB → 129 MiB | 139,923 → 3,881,730 | — | 0/0 |
| m6_scifact | yes | 7 / — | 10 / 12 | 0.3162 → 0.552 | 90 MiB → 101 MiB | 17,501 → 64,068 | 8 | 3/3 |
| m7_classification | yes | 7 / — | 10 / 13 | 0.2716 → 0.4471 | 87 MiB → 98 MiB | 18,410 → 69,271 | — | 0/0 |
| m7_overlay | yes | 13 / — | 18 / 28 | 0.5315 → 0.6318 | 98 MiB → 113 MiB | 34,667 → 132,734 | — | 10/10 |
| m9_pdf_financial | yes | 5 / — | 9 / 20 | 0.2072 → 0.4003 | 81 MiB → 94 MiB | 11,397 → 93,694 | — | 2/2 |
| m9_docx_financial | yes | 5 / — | 9 / 19 | 0.1772 → 0.3998 | 81 MiB → 94 MiB | 11,398 → 93,044 | — | 2/2 |

Analysis JSON mismatches: none.
