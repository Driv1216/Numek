import pandas as pd

from datatrust import DataTrust
from datatrust.narrative import build_narrative


def _write_dataset(tmp_path, data, name="data.csv"):
    path = tmp_path / name
    pd.DataFrame(data).to_csv(path, index=False)
    return path


def test_capped_score_exposes_evidence_to_final_score_path(tmp_path):
    path = _write_dataset(tmp_path, {"feature": range(10), "label": [0, 1] * 5})
    result = DataTrust(str(path), target="label").analyze()
    capped_scores = {
        **result["scores"],
        "evidence_score": 93.0,
        "overall": 69.0,
        "risk_level": "Elevated",
        "guardrails": [
            {
                "code": "severe_feature_missingness",
                "cap": 69.0,
                "explanation": "Feature columns require resolution: Cabin",
            }
        ],
    }

    narrative = build_narrative(
        result["profile"], capped_scores, result["risks"], result["findings"]
    )

    assert "Evidence score 93.0 → final score 69.0" in narrative["score_explanation"]
    assert "cap 69.0" in narrative["score_explanation"]
    assert "Cabin" in narrative["score_explanation"]


def test_uncapped_score_states_that_no_guardrail_changed_it(tmp_path):
    path = _write_dataset(tmp_path, {"feature": range(10), "label": [0, 1] * 5})

    result = DataTrust(str(path), target="label").analyze()

    assert result["scores"]["evidence_score"] == result["scores"]["overall"]
    assert "No guardrail changed the evidence score" in result["narrative"][
        "score_explanation"
    ]


def test_missingness_concentration_language_uses_exact_seventy_percent_rule(tmp_path):
    concentrated_path = _write_dataset(
        tmp_path,
        {
            "dominant": [None] * 7 + [1] * 3,
            "other": [None] * 3 + [1] * 7,
            "label": [0, 1] * 5,
        },
        "concentrated.csv",
    )
    spread_path = _write_dataset(
        tmp_path,
        {
            "largest": [None] * 6 + [1] * 4,
            "other": [None] * 4 + [1] * 6,
            "label": [0, 1] * 5,
        },
        "spread.csv",
    )

    concentrated = DataTrust(str(concentrated_path), target="label").analyze()
    spread = DataTrust(str(spread_path), target="label").analyze()

    assert "concentrated in dominant" in concentrated["narrative"][
        "missingness_interpretation"
    ]
    assert "70.0%" in concentrated["narrative"]["missingness_interpretation"]
    assert "spread across 2 columns" in spread["narrative"][
        "missingness_interpretation"
    ]


def test_missingness_minimal_rule_precedes_concentration(tmp_path):
    minimal_path = _write_dataset(
        tmp_path,
        {
            "dominant": [None] + list(range(1, 100)),
            "complete": list(range(100)),
            "label": [0, 1] * 50,
        },
        "minimal.csv",
    )
    boundary_path = _write_dataset(
        tmp_path,
        {
            "dominant": [None] + list(range(1, 100)),
            "label": [0, 1] * 50,
        },
        "boundary.csv",
    )

    minimal = DataTrust(str(minimal_path), target="label").analyze()["narrative"][
        "missingness_interpretation"
    ]
    boundary = DataTrust(str(boundary_path), target="label").analyze()["narrative"][
        "missingness_interpretation"
    ]

    assert minimal == (
        "Missingness is minimal: 1 of 200 feature cells (0.5%) are missing, "
        "affecting 1.0% of rows."
    )
    assert "concentrated in dominant" in boundary
    assert "100.0% of all missing feature cells" in boundary


def test_positive_interpretations_keep_detection_boundaries(tmp_path):
    path = _write_dataset(tmp_path, {"feature": range(10), "label": [0, 1] * 5})

    result = DataTrust(str(path), target="label").analyze()
    narrative = result["narrative"]

    assert narrative["duplicate_interpretation"].startswith(
        "No exact duplicate rows were detected."
    )
    assert "No name-based leakage candidates were detected" in narrative[
        "leakage_interpretation"
    ]
    assert "does not verify when every feature becomes available" in narrative[
        "leakage_interpretation"
    ]
    assert "below the current 75% target-imbalance finding threshold" in narrative[
        "target_interpretation"
    ]
    assert "does not establish model quality" in narrative["target_interpretation"]
