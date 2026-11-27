# Reproduce DataTrust qualification evidence

Run from `/Users/drivyaanshyadav/Desktop/Numek` with DataTrust and the relevant workflow extras installed. The active JSON files directly under each dataset's `configurations/` directory point to existing files in this repository. [Dataset folders](../README.md) · [Acceptance ledger](../evaluation/ACCEPTANCE.md).

## Replay an active configuration

Choose a configuration from the dataset folder. The examples replay the Real Estate regression and BEA same-vintage comparison directly through the product. The output directory is optional for an analytical check. To save results, create a fresh attempt directory and use its path in `generate_artifacts`.

```sh
cd /Users/drivyaanshyadav/Desktop/Numek
python -c "$(cat <<'PY'
import json
from pathlib import Path
from datatrust import (
    AnalysisConfig, CrossRepresentationAnalysisConfig, CrossRepresentationAuditSpec,
    DataTrust, DatasetSpec, TaskSpec,
)

root = Path.cwd() / "datasets"
path = root / "regression/uci_real_estate/configurations/real_estate_price.json"
config = json.loads(path.read_text())
regression = DataTrust.from_spec(
    DatasetSpec(**config["dataset"]),
    TaskSpec.from_dict(config["task"]),
    AnalysisConfig.from_dict(config["analysis"]),
).analyze_result()
print(regression.to_dict()["profile"]["row_count"])

path = root / "cross_representation/bea_gdp_2024q4/configurations/bea_same_vintage.json"
config = json.loads(path.read_text())
bea = DataTrust.audit_cross_representation(
    CrossRepresentationAuditSpec.from_dict(config["spec"]),
    CrossRepresentationAnalysisConfig.from_dict(config["options"]),
)
print(bea.to_dict()["profile"]["documents"])
PY
)"
```

Temporal and image configurations pass `spec` and `analysis` to `audit_temporal` or `audit_images` with the corresponding contract classes. Text passes `spec` and `options` to `audit_text`. Some retained scale configurations also describe how a Parquet source was read in bounded files or row groups. Follow the attempt's recorded scope when comparing populations, limits or fingerprints. A new execution receives its own revision and artifacts. The three optional M6 and M7 model configurations reuse existing runtime weights in the repository's `validation/m6/models/multilingual-e5-small` and `validation/m7/models/dinov2-base` directories.

## Recover protected evidence

Generate a native report and its analysis JSON in the same fresh attempt directory. This generates a protected manifest under `.datatrust-private/<audit-id>/manifest.json`. Use an evidence reference from that analysis and allow only the relevant dataset folder or the local library. The resolver checks the report binding and source identity before disclosure. Omitting the reveal flags returns locator information. To reopen the verified closeout evidence, use the matching reference and manifest from the integrity receipt. [Verified bindings](../evaluation/targeted_closeout_integrity.json).

```sh
datatrust text-evidence --manifest "$manifest" --report "$analysis_json" \
  --ref "$evidence_ref" --data-root "$PWD/datasets" --show-content --max-chars 64

datatrust image-evidence --manifest "$manifest" --report "$analysis_json" \
  --ref "$evidence_ref" --data-root "$PWD/datasets" --show-image --overlays
```

Keep the archive sealed. Historical attempt configurations and protected manifests bind the original paths and source identities. The original exports, receipts and any failed attempts remain in each dataset's report folders. Create a new binding by replaying the active configuration when a historical locator depends on a moved path. The original reusable configuration bytes are under each dataset's `configurations/baseline/`. The original campaign commands and harness are historical references. [Original runner notes](BASELINE.md) · [Relocation hashes](../manifests/relocation.json).
