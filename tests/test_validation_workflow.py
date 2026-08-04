import pandas as pd

from validation.mutate import build_mutations
from validation.run_validation import MUTATION_EXPECTATIONS


def test_controlled_mutation_suite_is_complete_and_deterministic():
    base = pd.DataFrame(
        {
            "workclass": ["private", "public"] * 3000,
            "annual_income_over_50k": ["no", "yes"] * 3000,
        }
    )

    first = build_mutations(base)
    second = build_mutations(base)

    assert set(first) == set(MUTATION_EXPECTATIONS)
    for name in first:
        pd.testing.assert_frame_equal(first[name], second[name])


def test_controlled_mutations_have_expected_structural_effects():
    base = pd.DataFrame(
        {
            "workclass": ["private", "public"] * 3000,
            "annual_income_over_50k": ["no", "yes"] * 3000,
        }
    )
    mutations = build_mutations(base)

    assert mutations["feature_missingness_100"]["workclass"].isna().all()
    assert len(mutations["duplicates"]) > len(base)
    assert mutations["target_imbalance"]["annual_income_over_50k"].value_counts().max() > 2500
    assert "post_income_outcome" in mutations["strong_leakage"]
    assert "employment_status" in mutations["review_only_leakage"]
    assert mutations["missing_targets"]["annual_income_over_50k"].isna().any()
    assert mutations["constant_field"]["validation_constant"].nunique() == 1
    conflict_features = [
        column for column in mutations["conflicting_labels"].columns
        if column != "annual_income_over_50k"
    ]
    conflict_counts = mutations["conflicting_labels"].groupby(
        conflict_features, dropna=False
    )["annual_income_over_50k"].nunique()
    assert (conflict_counts > 1).any()
