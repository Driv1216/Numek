import pytest

from datatrust.wording import agree, be_verb, count_phrase, have_verb, pluralize


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "rows"), (1, "row"), (2, "rows"), (25, "rows")],
)
def test_pluralize_handles_zero_singular_plural_and_larger_counts(count, expected):
    assert pluralize(count, "row") == expected


def test_count_phrases_and_verbs_are_deterministic():
    assert count_phrase(1, "class", "classes") == "1 class"
    assert count_phrase(2, "class", "classes") == "2 classes"
    assert have_verb(1) == "has"
    assert have_verb(2) == "have"
    assert be_verb(1, past=True) == "was"
    assert be_verb(0, past=True) == "were"
    assert agree(1, "contains", "contain") == "contains"
    assert agree(3, "contains", "contain") == "contain"
