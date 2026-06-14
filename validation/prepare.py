import argparse
import hashlib
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from validation.config import PREPARED_ROOT, RAW_ROOT, VALIDATION_ROOT, ensure_directories


GERMAN_COLUMNS = [
    "checking_account_status",
    "duration_months",
    "credit_history",
    "purpose",
    "credit_amount",
    "savings_status",
    "employment_duration",
    "installment_rate",
    "personal_status_sex",
    "other_debtors",
    "residence_duration",
    "property",
    "age",
    "other_installment_plans",
    "housing",
    "existing_credits",
    "job",
    "dependents",
    "telephone",
    "foreign_worker",
    "credit_risk",
]

ADULT_COLUMNS = [
    "age",
    "workclass",
    "final_weight",
    "education",
    "education_years",
    "marital_status",
    "occupation",
    "relationship",
    "race",
    "sex",
    "capital_gain",
    "capital_loss",
    "hours_per_week",
    "native_country",
    "annual_income_over_50k",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sources() -> dict:
    return json.loads((VALIDATION_ROOT / "sources.json").read_text(encoding="utf-8"))["datasets"]


def download_archives(sources: dict) -> None:
    for name, source in sources.items():
        destination = RAW_ROOT / source["archive"]
        if destination.exists():
            continue
        print(f"Downloading {name} from {source['url']}")
        urllib.request.urlretrieve(source["url"], destination)


def verify_archives(sources: dict) -> dict:
    checksums = {}
    for name, source in sources.items():
        archive = RAW_ROOT / source["archive"]
        if not archive.exists():
            raise FileNotFoundError(
                f"Missing {archive}. Run with --download or place the pinned UCI archive there."
            )
        actual = sha256(archive)
        expected = source.get("archive_sha256")
        if expected and actual != expected:
            raise ValueError(f"Checksum mismatch for {name}: expected {expected}, got {actual}")
        checksums[name] = actual
    return checksums


def prepare_german_credit(extracted: Path) -> pd.DataFrame:
    data = pd.read_csv(extracted / "german.data", sep=r"\s+", names=GERMAN_COLUMNS)
    data["credit_risk"] = data["credit_risk"].map({1: "good", 2: "bad"})
    return data


def prepare_bank_marketing(extracted: Path) -> pd.DataFrame:
    source_path = extracted / "bank" / "bank-full.csv"
    if not source_path.exists():
        inner_archive = extracted / "bank.zip"
        if not inner_archive.exists():
            raise FileNotFoundError("The Bank Marketing archive does not contain bank-full.csv or bank.zip.")
        inner_root = extracted / "bank_inner"
        inner_root.mkdir()
        with zipfile.ZipFile(inner_archive) as bundle:
            bundle.extractall(inner_root)
        source_path = inner_root / "bank-full.csv"
    data = pd.read_csv(source_path, sep=";")
    return data.rename(
        columns={
            "poutcome": "previous_campaign_outcome",
            "y": "subscribed_term_deposit",
        }
    )


def _read_adult_file(path: Path, skiprows: int = 0) -> pd.DataFrame:
    return pd.read_csv(
        path,
        names=ADULT_COLUMNS,
        skiprows=skiprows,
        skipinitialspace=True,
        na_values=["?"],
    )


def prepare_adult(extracted: Path) -> pd.DataFrame:
    train = _read_adult_file(extracted / "adult.data")
    test = _read_adult_file(extracted / "adult.test", skiprows=1)
    test["annual_income_over_50k"] = test["annual_income_over_50k"].str.rstrip(".")
    return pd.concat([train, test], ignore_index=True)


PREPARERS = {
    "german_credit": prepare_german_credit,
    "bank_marketing": prepare_bank_marketing,
    "adult": prepare_adult,
}


def prepare_all(download: bool = False) -> dict:
    ensure_directories()
    sources = load_sources()
    if download:
        download_archives(sources)
    archive_checksums = verify_archives(sources)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "datasets": {},
    }
    for name, source in sources.items():
        archive = RAW_ROOT / source["archive"]
        with TemporaryDirectory() as temporary:
            extracted = Path(temporary)
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(extracted)
            data = PREPARERS[name](extracted)

        destination = PREPARED_ROOT / source["prepared_file"]
        data.to_csv(destination, index=False)
        manifest["datasets"][name] = {
            "archive_sha256": archive_checksums[name],
            "prepared_path": str(destination.relative_to(VALIDATION_ROOT)),
            "prepared_sha256": sha256(destination),
            "rows": int(len(data)),
            "columns": int(len(data.columns)),
            "target": data.columns[-1],
        }
        print(f"Prepared {name}: {len(data)} rows x {len(data.columns)} columns")

    manifest_path = PREPARED_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare the pinned UCI validation datasets.")
    parser.add_argument("--download", action="store_true", help="Download missing UCI archives.")
    args = parser.parse_args()
    prepare_all(download=args.download)


if __name__ == "__main__":
    main()
