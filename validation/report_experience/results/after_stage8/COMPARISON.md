# Report Experience — before versus after_stage8

| Case | Analysis JSON identical | Pages before (canonical / app) | Pages after (focused / complete) | PDF s before (canonical) → focused | Peak PDF RSS before → focused | HTML before → after (focused) | Pages < 40% fill after (focused, excl. last) | Finding titles in PDF (focused) |
|---|---|---|---|---|---|---|---|---|
| german_credit | yes | 16 / 14 | 16 / 17 | 0.6552 → 0.8909 | 110 MiB → 112 MiB | 43,430 → 90,244 | 12 | 2/2 |
| bank_full | yes | 17 / 15 | 18 / 19 | 0.7222 → 0.9736 | 111 MiB → 114 MiB | 46,363 → 97,752 | — | 3/3 |
| bank_full_declared | yes | 19 / 17 | 20 / 21 | 0.8395 → 0.9642 | 115 MiB → 118 MiB | 51,774 → 103,161 | — | 3/3 |
| german_unlabeled | yes | 13 / — | 12 / 16 | 0.6871 → 0.6169 | 106 MiB → 102 MiB | 40,211 → 89,431 | 6 | 2/2 |
| mutation_strong_leakage | yes | 20 / — | 21 / 22 | 0.8126 → 1.0219 | 113 MiB → 115 MiB | 50,789 → 100,799 | 14 | 4/4 |
| mutation_feature_missingness_100 | yes | 23 / — | 23 / 23 | 0.9938 → 1.0351 | 115 MiB → 119 MiB | 55,008 → 108,975 | 15 | 6/6 |
| mutation_duplicates | yes | 20 / — | 20 / 21 | 0.8675 → 0.9969 | 113 MiB → 116 MiB | 51,029 → 99,768 | — | 5/5 |
| wide_200 | yes | 27 / 26 | 13 / 33 | 2.3185 → 0.631 | 221 MiB → 103 MiB | 96,221 → 157,299 | 9 | 0/0 |
| wide_1000 | yes | 92 / 91 | 13 / 122 | 10.7212 → 0.6448 | 734 MiB → 103 MiB | 370,061 → 526,103 | 9 | 0/0 |
| wide_5000 | yes | 417 / 416 | 13 / 564 | 50.6401 → 0.7067 | 2,362 MiB → 107 MiB | 1,751,508 → 2,402,253 | 9 | 0/0 |
| wide_flagged_1000 | yes | 128 / 126 | 29 / 146 | 11.0017 → 1.5335 | 837 MiB → 147 MiB | 460,351 → 677,021 | 19 | 4/4 |
| tall_1m | yes | 12 / — | 15 / 15 | 0.5021 → 0.6753 | 101 MiB → 105 MiB | 35,549 → 78,659 | 8, 11 | 1/1 |
| bike_hour | yes | 27 / — | 21 / 33 | 1.4854 → 0.9829 | 134 MiB → 120 MiB | 76,059 → 143,490 | 12 | 3/3 |
| m3_scene | yes | 11 / — | 14 / 20 | 0.4315 → 0.5921 | 101 MiB → 110 MiB | 26,739 → 98,490 | 10 | 2/2 |
| m4_contaminated | yes | 4 / — | 6 / 6 | 0.2091 → 0.3718 | 88 MiB → 95 MiB | 11,189 → 40,047 | — | 1/1 |
| m4_wide | yes | 4 / — | 6 / 9 | 0.2544 → 0.3694 | 87 MiB → 94 MiB | 11,146 → 51,411 | — | 2/2 |
| m4_long_headers | yes | 5 / — | 6 / 6 | 0.2048 → 0.3163 | 85 MiB → 90 MiB | 10,298 → 35,287 | — | 2/2 |
| m5_retail | yes | 10 / — | 10 / 85 | 0.5615 → 0.7537 | 104 MiB → 117 MiB | 122,050 → 613,402 | 6 | 2/2 |
| m5_beijing | yes | 10 / — | 11 / 160 | 0.5389 → 0.8049 | 105 MiB → 121 MiB | 131,833 → 1,090,168 | 7 | 15/15 |
| m5_long_headers | yes | 10 / — | 10 / 806 | 0.5759 → 0.8744 | 105 MiB → 128 MiB | 139,923 → 3,879,856 | — | 0/0 |
| m6_scifact | yes | 7 / — | 10 / 12 | 0.3162 → 0.5311 | 90 MiB → 100 MiB | 17,501 → 61,699 | 8 | 3/3 |
| m7_classification | yes | 7 / — | 10 / 13 | 0.2716 → 0.4326 | 87 MiB → 96 MiB | 18,410 → 66,964 | — | 0/0 |
| m7_overlay | yes | 13 / — | 18 / 28 | 0.5315 → 0.6078 | 98 MiB → 111 MiB | 34,667 → 129,305 | — | 10/10 |
| m9_pdf_financial | yes | 5 / — | 9 / 20 | 0.2072 → 0.3732 | 81 MiB → 92 MiB | 11,397 → 90,631 | — | 2/2 |
| m9_docx_financial | yes | 5 / — | 9 / 19 | 0.1772 → 0.3748 | 81 MiB → 92 MiB | 11,398 → 89,981 | — | 2/2 |

Analysis JSON mismatches: none.
