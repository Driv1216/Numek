from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VALIDATION_ROOT = ROOT / "validation"
DATA_ROOT = VALIDATION_ROOT / "data"
RAW_ROOT = DATA_ROOT / "raw"
PREPARED_ROOT = DATA_ROOT / "prepared"
MUTATION_ROOT = DATA_ROOT / "mutations"
REPORT_ROOT = VALIDATION_ROOT / "reports"
RESULT_ROOT = VALIDATION_ROOT / "results"
COMPARISON_ROOT = VALIDATION_ROOT / "comparison"

PUBLIC_DATASETS = {
    "german_credit": {
        "path": PREPARED_ROOT / "german_credit.csv",
        "target": "credit_risk",
    },
    "bank_marketing": {
        "path": PREPARED_ROOT / "bank_marketing.csv",
        "target": "subscribed_term_deposit",
    },
    "adult": {
        "path": PREPARED_ROOT / "adult.csv",
        "target": "annual_income_over_50k",
    },
}

MUTATION_TARGET = "annual_income_over_50k"

REPORT_SECTIONS = [
    "1. Decision Summary",
    "2. Priority Actions",
    "3. Dataset Overview",
    "4. Target and Label Evidence",
    "5. Missingness Evidence",
    "6. Duplicate and Feature Evidence",
    "7. Scoring, Methodology, and Limitations",
    "8. Technical Appendix",
]


def ensure_directories() -> None:
    for path in (
        RAW_ROOT,
        PREPARED_ROOT,
        MUTATION_ROOT,
        REPORT_ROOT,
        RESULT_ROOT,
        COMPARISON_ROOT,
    ):
        path.mkdir(parents=True, exist_ok=True)
